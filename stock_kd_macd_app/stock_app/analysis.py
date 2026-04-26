from __future__ import annotations

from dataclasses import dataclass

from .charting import render_trade_chart
from .data_source import DailyBar, OfficialStockDataSource, StockDataError
from .enrichment import StockEnrichmentService
from .indicators import (
    calculate_atr,
    calculate_kd,
    calculate_macd,
    calculate_sma,
    classify_curve,
    classify_direction,
    classify_zero_axis,
    detect_cross_down,
    detect_cross_up,
    detect_kd_signal,
)


@dataclass(frozen=True)
class AnalysisBundle:
    history: object
    series: dict
    summary: dict
    events: list[dict]


class StockAnalyzer:
    def __init__(self, data_source: OfficialStockDataSource, enrichment_service: StockEnrichmentService | None = None):
        self.data_source = data_source
        self.enrichment_service = enrichment_service or StockEnrichmentService(self.data_source, network_enabled=False)

    def analyze(self, symbol: str, target_price: float | None = None, stop_price: float | None = None) -> dict:
        return self._build_bundle(symbol, target_price=target_price, stop_price=stop_price).summary

    def render_chart(self, symbol: str) -> bytes:
        return render_trade_chart(self._build_bundle(symbol))

    def _build_bundle(
        self,
        symbol: str,
        target_price: float | None = None,
        stop_price: float | None = None,
    ) -> AnalysisBundle:
        history = self.data_source.get_history(symbol)
        if len(history.bars) < 121:
            raise StockDataError("資料不足，至少需要 121 根日線才能分析 MA120、KD 與 MACD。")

        closes = [bar.close_price for bar in history.bars]
        highs = [bar.high_price for bar in history.bars]
        lows = [bar.low_price for bar in history.bars]
        volumes = [bar.volume_lots for bar in history.bars]

        _, k_values, d_values = calculate_kd(closes, highs, lows, period=9)
        dif_values, dea_values, osc_values = calculate_macd(closes, short_period=12, long_period=26, signal_period=9)
        atr14_series = calculate_atr(highs, lows, closes, period=14)
        ma5_series = calculate_sma(closes, 5)
        ma10_series = calculate_sma(closes, 10)
        ma20_series = calculate_sma(closes, 20)
        ma60_series = calculate_sma(closes, 60)
        ma120_series = calculate_sma(closes, 120)
        vma5_series = calculate_sma(volumes, 5)
        vma20_series = calculate_sma(volumes, 20)

        series = {
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "k": k_values,
            "d": d_values,
            "dif": dif_values,
            "dea": dea_values,
            "osc": osc_values,
            "atr14": atr14_series,
            "ma5": ma5_series,
            "ma10": ma10_series,
            "ma20": ma20_series,
            "ma60": ma60_series,
            "ma120": ma120_series,
            "vma5": vma5_series,
            "vma20": vma20_series,
        }

        events, holding_position, active_exit_signals, active_exit_warnings, last_trade, last_entry_index = self._simulate_trades(
            history.bars,
            series,
        )
        latest_index = len(history.bars) - 1
        latest_snapshot = self._build_snapshot(history.bars, series, latest_index)
        support_resistance = self._build_support_resistance(history.bars, series, latest_index)
        risk_plan = self._build_risk_plan(latest_snapshot, support_resistance, target_price, stop_price)
        backtest = self._build_backtest(events)

        exit_analysis = {
            "holdingPosition": holding_position,
            "activeSignals": active_exit_signals,
            "activeWarnings": active_exit_warnings,
            "lastTrade": last_trade,
            "recentEvents": events[-8:],
            "rules": {
                "priceTrigger": self._round(latest_snapshot["ma5"]),
                "kdTrigger": "K 在 80 以上且跌破 D，或高檔開始向下彎曲",
                "volumeTrigger": "創高但量縮，或量能跌回 VMA5 下方",
                "trailingStopTrigger": "自波段高點回落 8%",
                "ma20Trigger": "跌破 MA20 且連續 3 日站不回",
            },
            "lastEntryIndex": last_entry_index,
        }

        try:
            intelligence = self.enrichment_service.build_intelligence(history, latest_snapshot, exit_analysis)
        except Exception:
            intelligence = StockEnrichmentService(self.data_source, network_enabled=False).build_intelligence(
                history,
                latest_snapshot,
                exit_analysis,
            )

        dashboard = self._build_dashboard(latest_snapshot, exit_analysis)
        status_tags = self._build_status_tags(latest_snapshot, intelligence, exit_analysis, risk_plan, backtest)
        signal_summary = f"策略分數 {latest_snapshot['score']['total']}/10，目前判定為「{latest_snapshot['decision']['label']}」。"
        entry_narrative = self._build_entry_narrative(latest_snapshot, intelligence, support_resistance, risk_plan, backtest)
        company_name = intelligence["companyProfile"]["displayName"].split(" (")[0]

        summary = {
            "symbol": history.symbol,
            "name": company_name,
            "market": history.market,
            "dataDate": history.bars[-1].trading_date.isoformat(),
            "latestClose": self._round(history.bars[-1].close_price),
            "latestVolumeLots": self._round(history.bars[-1].volume_lots),
            "movingAverages": {
                "ma5": self._round(latest_snapshot["ma5"]),
                "ma10": self._round(latest_snapshot["ma10"]),
                "ma20": self._round(latest_snapshot["ma20"]),
                "ma60": self._round(latest_snapshot["ma60"]),
                "ma120": self._round(latest_snapshot["ma120"]),
            },
            "movingAverageAnalysis": latest_snapshot["movingAverageAnalysis"],
            "volumeAverages": {
                "vma5": self._round(latest_snapshot["vma5"]),
                "vma20": self._round(latest_snapshot["vma20"]),
            },
            "volumeAnalysis": latest_snapshot["volumeAnalysis"],
            "k": self._round(latest_snapshot["k"]),
            "d": self._round(latest_snapshot["d"]),
            "dif": self._round(latest_snapshot["dif"]),
            "dea": self._round(latest_snapshot["dea"]),
            "osc": self._round(latest_snapshot["osc"]),
            "kdDirection": latest_snapshot["kdDirection"],
            "kdCurve": latest_snapshot["kdCurve"],
            "kdSignal": latest_snapshot["kdSignal"],
            "kdLowZone": latest_snapshot["kdLowZone"],
            "kdPass": latest_snapshot["kdPass"],
            "macdDirection": latest_snapshot["macdDirection"],
            "macdCurve": latest_snapshot["macdCurve"],
            "macdZeroAxis": latest_snapshot["macdZeroAxis"],
            "oscDirection": latest_snapshot["oscDirection"],
            "oscFlipPositive": latest_snapshot["oscFlipPositive"],
            "negativeBarsShortening": latest_snapshot["negativeBarsShortening"],
            "macdGoldCross": latest_snapshot["macdGoldCross"],
            "zeroAxisGoldCross": latest_snapshot["zeroAxisGoldCross"],
            "macdPass": latest_snapshot["macdPass"],
            "score": latest_snapshot["score"],
            "decision": latest_snapshot["decision"],
            "dashboard": dashboard,
            "signalSummary": signal_summary,
            "entryNarrative": entry_narrative,
            "supportResistance": support_resistance,
            "riskPlan": risk_plan,
            "backtest": backtest,
            "exitAnalysis": exit_analysis,
            "companyProfile": intelligence["companyProfile"],
            "peerComparison": intelligence["peerComparison"],
            "chipAnalysis": intelligence["chipAnalysis"],
            "fundamentals": intelligence["fundamentals"],
            "sentiment": intelligence["sentiment"],
            "statusTags": status_tags,
        }

        return AnalysisBundle(history=history, series=series, summary=summary, events=events)

    def _simulate_trades(
        self,
        bars: list[DailyBar],
        series: dict,
    ) -> tuple[list[dict], bool, list[str], list[str], dict | None, int | None]:
        events: list[dict] = []
        holding_position = False
        last_trade = None
        entry_index: int | None = None

        for index in range(120, len(bars)):
            snapshot = self._build_snapshot(bars, series, index)
            close_price = bars[index].close_price
            event_date = bars[index].trading_date.isoformat()

            if not holding_position and snapshot["score"]["total"] >= 7:
                holding_position = True
                entry_index = index
                event = {
                    "date": event_date,
                    "type": "buy",
                    "price": self._round(close_price),
                    "reason": f"{snapshot['decision']['label']}，分數 {snapshot['score']['total']}/10",
                }
                events.append(event)
                last_trade = event
                continue

            if holding_position:
                exit_signals, _warnings = self._evaluate_exit_signals(bars, series, index, entry_index)
                if exit_signals:
                    holding_position = False
                    event = {
                        "date": event_date,
                        "type": "sell",
                        "price": self._round(close_price),
                        "reason": "、".join(exit_signals),
                    }
                    events.append(event)
                    last_trade = event
                    entry_index = None

        active_exit_signals: list[str] = []
        active_exit_warnings: list[str] = []
        if holding_position:
            active_exit_signals, active_exit_warnings = self._evaluate_exit_signals(bars, series, len(bars) - 1, entry_index)

        return events, holding_position, active_exit_signals, active_exit_warnings, last_trade, entry_index

    def _build_snapshot(self, bars: list[DailyBar], series: dict, index: int) -> dict:
        ma5 = self._require_value(series["ma5"], index)
        ma10 = self._require_value(series["ma10"], index)
        ma20 = self._require_value(series["ma20"], index)
        ma60 = self._require_value(series["ma60"], index)
        ma120 = self._require_value(series["ma120"], index)
        prev_ma60 = self._require_value(series["ma60"], index - 1)
        prev_ma120 = self._require_value(series["ma120"], index - 1)
        vma5 = self._require_value(series["vma5"], index)
        vma20 = self._require_value(series["vma20"], index)

        close_price = bars[index].close_price
        volume = bars[index].volume_lots
        k_value = series["k"][index]
        dif_value = series["dif"][index]
        dea_value = series["dea"][index]
        osc_value = series["osc"][index]

        price_above_ma5 = close_price > ma5
        bullish_stack = ma5 > ma10 > ma20
        ma60_direction = self._classify_ma_slope(ma60, prev_ma60)
        ma120_direction = self._classify_ma_slope(ma120, prev_ma120)
        long_trend_support = ma60_direction in {"上行", "走平"} and ma120_direction in {"上行", "走平"}
        ma_pass = price_above_ma5 and bullish_stack and long_trend_support

        kd_signal = detect_kd_signal(series["k"][: index + 1], series["d"][: index + 1])
        kd_direction = classify_direction(series["k"][: index + 1], min_threshold=0.15)
        kd_curve = classify_curve(series["k"][: index + 1], min_threshold=0.2)
        kd_low_zone = k_value < 30.0
        kd_upturn = index > 0 and k_value > series["k"][index - 1]
        kd_pass = kd_low_zone and (kd_upturn or kd_signal == "黃金交叉")

        macd_direction = classify_direction(series["dif"][: index + 1], min_threshold=0.05)
        macd_curve = classify_curve(series["dif"][: index + 1], min_threshold=0.08)
        macd_zero_axis = classify_zero_axis(dif_value, min_threshold=0.05)
        osc_direction = classify_zero_axis(osc_value, min_threshold=0.05)
        macd_gold_cross = index > 0 and detect_cross_up(series["dif"][index - 1 : index + 1], series["dea"][index - 1 : index + 1])
        zero_axis_gold_cross = macd_gold_cross and dif_value > 0 and dea_value > 0
        osc_flip_positive = index > 0 and series["osc"][index - 1] <= 0 < osc_value
        negative_bars_shortening = (
            index >= 2
            and series["osc"][index - 2] < 0
            and series["osc"][index - 1] < 0
            and osc_value < 0
            and series["osc"][index - 2] < series["osc"][index - 1] < osc_value
        )
        macd_pass = osc_flip_positive or macd_gold_cross or negative_bars_shortening

        volume_ratio_to_vma5 = volume / vma5 if vma5 else 0.0
        volume_above_vma20 = volume > vma20
        volume_burst = volume > (vma5 * 1.5)
        volume_pass = volume_burst and volume_above_vma20

        score = {
            "ma": 3 if ma_pass else 0,
            "kd": 2 if kd_pass else 0,
            "macd": 2 if macd_pass else 0,
            "volume": 3 if volume_pass else 0,
        }
        score["total"] = score["ma"] + score["kd"] + score["macd"] + score["volume"]

        decision = {"label": self._decision_label(score["total"]), "action": self._decision_action(score["total"])}

        return {
            "close": close_price,
            "volume": volume,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "ma120": ma120,
            "vma5": vma5,
            "vma20": vma20,
            "k": k_value,
            "d": series["d"][index],
            "dif": dif_value,
            "dea": dea_value,
            "osc": osc_value,
            "kdDirection": kd_direction,
            "kdCurve": kd_curve,
            "kdSignal": kd_signal,
            "kdLowZone": kd_low_zone,
            "kdPass": kd_pass,
            "macdDirection": macd_direction,
            "macdCurve": macd_curve,
            "macdZeroAxis": macd_zero_axis,
            "oscDirection": osc_direction,
            "oscFlipPositive": osc_flip_positive,
            "negativeBarsShortening": negative_bars_shortening,
            "macdGoldCross": macd_gold_cross,
            "zeroAxisGoldCross": zero_axis_gold_cross,
            "macdPass": macd_pass,
            "movingAverageAnalysis": {
                "priceAboveMa5": price_above_ma5,
                "bullishStack": bullish_stack,
                "ma60Direction": ma60_direction,
                "ma120Direction": ma120_direction,
                "longTrendSupport": long_trend_support,
                "pass": ma_pass,
            },
            "volumeAnalysis": {
                "ratioToVma5": self._round(volume_ratio_to_vma5),
                "aboveVma20": volume_above_vma20,
                "burst": volume_burst,
                "pass": volume_pass,
            },
            "score": score,
            "decision": decision,
        }

    def _build_support_resistance(self, bars: list[DailyBar], series: dict, index: int) -> dict:
        recent_bars = bars[max(0, index - 59) : index + 1]
        atr14 = self._require_value(series["atr14"], index)
        ma20 = self._require_value(series["ma20"], index)
        close_price = bars[index].close_price

        quarter_high = max(bar.high_price for bar in recent_bars)
        quarter_low = min(bar.low_price for bar in recent_bars)
        max_volume_bar = max(recent_bars, key=lambda item: item.volume_lots)
        bullish_bars = [bar for bar in recent_bars if bar.close_price > bar.open_price]
        key_bull_bar = max(bullish_bars or recent_bars, key=lambda item: ((item.close_price - item.open_price), item.volume_lots))

        atr_stop = close_price - (2 * atr14)
        support_candidates = sorted(
            {round(value, 4) for value in [ma20, max_volume_bar.low_price, key_bull_bar.low_price, atr_stop, quarter_low] if value < close_price},
            reverse=True,
        )
        suggested_stop = support_candidates[0] if support_candidates else atr_stop

        return {
            "atr14": self._round(atr14),
            "atrStopLoss": self._round(atr_stop),
            "suggestedStopLoss": self._round(suggested_stop),
            "quarterHighResistance": self._round(quarter_high),
            "quarterLowSupport": self._round(quarter_low),
            "maxVolumeSupport": self._round(max_volume_bar.low_price),
            "keyBullBarSupport": self._round(key_bull_bar.low_price),
            "ma20Support": self._round(ma20),
        }

    def _build_risk_plan(
        self,
        snapshot: dict,
        support_resistance: dict,
        target_price: float | None,
        stop_price: float | None,
    ) -> dict:
        close_price = snapshot["close"]
        effective_stop = stop_price if stop_price is not None else support_resistance["suggestedStopLoss"]
        effective_target = target_price if target_price is not None else max(close_price, support_resistance["quarterHighResistance"])

        risk_amount = None
        reward_amount = None
        rr_ratio = None
        valid = False
        note = "可自行輸入目標價與停損價，系統會自動換算風險報酬比。"

        if effective_stop is not None and effective_target is not None:
            risk_amount = close_price - effective_stop
            reward_amount = effective_target - close_price
            if risk_amount > 0 and reward_amount > 0:
                rr_ratio = reward_amount / risk_amount
                valid = True
                if rr_ratio >= 3:
                    note = "這筆交易的風險報酬比達標，條件算健康。"
                elif rr_ratio >= 2:
                    note = "風險報酬比尚可，但還不到特別漂亮。"
                else:
                    note = "目前報酬空間偏小，容易出現追價不划算。"
            else:
                note = "目標價需高於現價，停損價需低於現價，風險報酬比才有意義。"

        return {
            "targetPrice": self._round(effective_target),
            "stopPrice": self._round(effective_stop),
            "riskAmount": self._round(risk_amount),
            "rewardAmount": self._round(reward_amount),
            "rrRatio": self._round(rr_ratio),
            "valid": valid,
            "note": note,
        }

    def _build_backtest(self, events: list[dict]) -> dict:
        returns = []
        last_buy = None
        for event in events:
            if event["type"] == "buy":
                last_buy = event
            elif event["type"] == "sell" and last_buy:
                buy_price = float(last_buy["price"])
                sell_price = float(event["price"])
                if buy_price > 0:
                    returns.append(((sell_price - buy_price) / buy_price) * 100)
                last_buy = None

        closed_trades = len(returns)
        winning_trades = sum(1 for value in returns if value > 0)
        win_rate = (winning_trades / closed_trades) * 100 if closed_trades else None
        avg_return = sum(returns) / closed_trades if closed_trades else None

        return {
            "closedTrades": closed_trades,
            "winningTrades": winning_trades,
            "winRate": self._round(win_rate),
            "avgReturn": self._round(avg_return),
            "bestTrade": self._round(max(returns)) if returns else None,
            "worstTrade": self._round(min(returns)) if returns else None,
            "note": "這裡是用目前策略規則回放歷史訊號，屬於參考，不代表未來績效。",
        }

    def _evaluate_exit_signals(
        self,
        bars: list[DailyBar],
        series: dict,
        index: int,
        entry_index: int | None,
    ) -> tuple[list[str], list[str]]:
        signals: list[str] = []
        warnings: list[str] = []

        close_price = bars[index].close_price
        ma5 = self._require_value(series["ma5"], index)
        ma10 = self._require_value(series["ma10"], index)
        ma20 = self._require_value(series["ma20"], index)
        prev_ma5 = self._require_value(series["ma5"], index - 1)
        prev_ma10 = self._require_value(series["ma10"], index - 1)
        volume = bars[index].volume_lots
        vma5 = self._require_value(series["vma5"], index)

        if close_price < ma5:
            signals.append("跌破 MA5")
        if prev_ma5 >= prev_ma10 and ma5 < ma10:
            signals.append("MA5 下穿 MA10")

        k_series = series["k"][: index + 1]
        d_series = series["d"][: index + 1]
        dif_series = series["dif"][: index + 1]
        dea_series = series["dea"][: index + 1]
        osc_series = series["osc"][: index + 1]

        k_value = k_series[-1]
        if k_value > 80 and detect_cross_down(k_series[-2:], d_series[-2:]):
            signals.append("KD 高檔死叉")
        elif k_value > 80 and classify_curve(k_series, min_threshold=0.2) == "向下彎曲":
            signals.append("KD 高檔下彎")

        if detect_cross_down(dif_series[-2:], dea_series[-2:]):
            signals.append("MACD 死叉")
        elif len(osc_series) >= 2 and osc_series[-1] < osc_series[-2] and osc_series[-1] > 0:
            warnings.append("MACD 紅柱收斂")

        recent_high = max(bar.close_price for bar in bars[max(0, index - 4) : index + 1])
        previous_high = max(bar.close_price for bar in bars[max(0, index - 9) : index]) if index >= 1 else recent_high
        if close_price >= recent_high and close_price > previous_high and volume < vma5:
            signals.append("高檔量價背離")
        elif volume < vma5:
            warnings.append("量能低於 VMA5")

        if entry_index is not None:
            peak_close = max(bar.close_price for bar in bars[entry_index : index + 1])
            if peak_close > 0:
                drawdown_pct = ((peak_close - close_price) / peak_close) * 100
                if drawdown_pct >= 8:
                    signals.append("自高點回落 8%")

        if index >= 2:
            closes_3d = [bars[index - offset].close_price for offset in [2, 1, 0]]
            ma20_3d = [self._require_value(series["ma20"], index - offset) for offset in [2, 1, 0]]
            if all(close < ma for close, ma in zip(closes_3d, ma20_3d)):
                signals.append("跌破 MA20 三日未回")
            elif close_price < ma20:
                warnings.append("跌破 MA20")

        return list(dict.fromkeys(signals)), list(dict.fromkeys(warnings))

    def _build_dashboard(self, snapshot: dict, exit_analysis: dict) -> dict:
        score = snapshot["score"]["total"]
        if exit_analysis["activeSignals"]:
            return {"tone": "danger", "label": "偏空警戒", "headline": "先看風險控管", "scoreHint": f"{score}/10"}
        if score >= 9:
            return {"tone": "positive", "label": "多頭強勢", "headline": "趨勢、動能、量能同步", "scoreHint": f"{score}/10"}
        if score >= 7:
            return {"tone": "warning", "label": "偏多觀察", "headline": "可以分批布局，但還要盯量價", "scoreHint": f"{score}/10"}
        return {"tone": "danger", "label": "觀望為主", "headline": "條件不夠整齊，先別急著追", "scoreHint": f"{score}/10"}

    def _build_status_tags(
        self,
        snapshot: dict,
        intelligence: dict,
        exit_analysis: dict,
        risk_plan: dict,
        backtest: dict,
    ) -> list[dict]:
        tags: list[dict] = []
        ma_analysis = snapshot["movingAverageAnalysis"]
        volume_analysis = snapshot["volumeAnalysis"]

        if ma_analysis["bullishStack"]:
            tags.append({"label": "#多頭排列", "tone": "positive"})
        if volume_analysis["burst"] and snapshot["close"] > snapshot["ma5"]:
            tags.append({"label": "#量增價揚", "tone": "positive"})
        if risk_plan["valid"] and (risk_plan["rrRatio"] or 0) >= 3:
            tags.append({"label": "#風報比達標", "tone": "positive"})
        if (backtest["winRate"] or 0) >= 55:
            tags.append({"label": "#回測勝率不差", "tone": "positive"})

        for label in intelligence["chipAnalysis"].get("tags", []):
            tags.append({"label": label, "tone": "positive"})

        if not ma_analysis["priceAboveMa5"]:
            tags.append({"label": "#跌破五日線", "tone": "danger"})
        if snapshot["k"] > 80:
            tags.append({"label": "#KD過熱", "tone": "danger"})
        if any("背離" in signal for signal in exit_analysis["activeSignals"]):
            tags.append({"label": "#量價背離", "tone": "danger"})
        if not exit_analysis["activeSignals"] and not exit_analysis["activeWarnings"]:
            tags.append({"label": "#持股監控中", "tone": "neutral"})

        seen: set[str] = set()
        result = []
        for tag in tags:
            if tag["label"] not in seen:
                result.append(tag)
                seen.add(tag["label"])
        return result

    def _build_entry_narrative(
        self,
        snapshot: dict,
        intelligence: dict,
        support_resistance: dict,
        risk_plan: dict,
        backtest: dict,
    ) -> str:
        parts = []

        if snapshot["movingAverageAnalysis"]["pass"]:
            parts.append("均線系統已經站穩五日線，短中期結構偏多。")
        else:
            parts.append("均線結構還不夠整齊，先把 MA5 與多頭排列當作第一關。")

        if snapshot["kdPass"]:
            parts.append("KD 在低檔有轉強跡象，短線動能開始回來。")
        else:
            parts.append("KD 還沒有形成漂亮的低檔轉強，追價要保守。")

        if snapshot["macdPass"]:
            parts.append("MACD 動能有切換訊號，適合搭配量能一起看。")
        else:
            parts.append("MACD 還在整理，代表攻擊力道不算完整。")

        parts.append(
            f"目前 ATR14 約 {support_resistance['atr14']:.2f}，建議停損可先參考 {support_resistance['suggestedStopLoss']:.2f}。"
        )
        parts.append(
            f"近一季壓力先看 {support_resistance['quarterHighResistance']:.2f}，關鍵支撐看 {support_resistance['maxVolumeSupport']:.2f}。"
        )

        if risk_plan["valid"] and risk_plan["rrRatio"] is not None:
            parts.append(f"依目前設定換算，風險報酬比約 {risk_plan['rrRatio']:.2f}。")

        if backtest["closedTrades"]:
            parts.append(f"近一段回測共 {backtest['closedTrades']} 筆已平倉交易，勝率約 {backtest['winRate']:.2f}%。")

        chip_narrative = intelligence["chipAnalysis"].get("narrative")
        if chip_narrative:
            parts.append(chip_narrative)

        return " ".join(parts)

    def _decision_label(self, total_score: int) -> str:
        if total_score >= 9:
            return "強力入場"
        if total_score >= 7:
            return "分批布局"
        return "觀望過濾"

    def _decision_action(self, total_score: int) -> str:
        if total_score >= 9:
            return "四項條件幾乎同步，偏向強勢攻擊型態，但還是要守停損。"
        if total_score >= 7:
            return "趨勢有成形，可以小量布局，等量能或 MACD 再補強。"
        return "先觀察，不要因為單一指標上彎就急著追。"

    def _classify_ma_slope(self, current: float, previous: float) -> str:
        delta = current - previous
        if abs(delta) <= max(0.05, abs(current) * 0.0005):
            return "走平"
        return "上行" if delta > 0 else "下行"

    def _require_value(self, series: list[float | None], index: int) -> float:
        value = series[index]
        if value is None:
            raise StockDataError("資料不足，指標尚未成熟。")
        return float(value)

    def _round(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(float(value), 2)
