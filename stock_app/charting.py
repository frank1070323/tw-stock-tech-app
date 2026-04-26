from __future__ import annotations

from io import BytesIO

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
from matplotlib import font_manager


_FONT_PROP = None
for font_path in [
    r"C:\Windows\Fonts\msjh.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\mingliu.ttc",
]:
    try:
        font_manager.fontManager.addfont(font_path)
        if _FONT_PROP is None:
            _FONT_PROP = font_manager.FontProperties(fname=font_path)
    except OSError:
        pass

matplotlib.rcParams["font.family"] = ["Microsoft JhengHei", "Microsoft YaHei", "MingLiU", "DejaVu Sans"]
matplotlib.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "MingLiU", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


def render_trade_chart(bundle) -> bytes:
    bars = bundle.history.bars
    series = bundle.series
    events = bundle.events
    summary = bundle.summary

    recent_bars = bars[-160:]
    start_index = len(bars) - len(recent_bars)
    recent_dates = [bar.trading_date for bar in recent_bars]
    visible_dates = {day.isoformat() for day in recent_dates}
    index = pd.DatetimeIndex(recent_dates)

    df = pd.DataFrame(
        {
            "Open": [bar.open_price for bar in recent_bars],
            "High": [bar.high_price for bar in recent_bars],
            "Low": [bar.low_price for bar in recent_bars],
            "Close": [bar.close_price for bar in recent_bars],
            "Volume": [bar.volume_lots for bar in recent_bars],
            "MA5": _slice(series["ma5"], start_index),
            "MA10": _slice(series["ma10"], start_index),
            "MA20": _slice(series["ma20"], start_index),
            "MA60": _slice(series["ma60"], start_index),
            "MA120": _slice(series["ma120"], start_index),
            "DIF": _slice(series["dif"], start_index),
            "DEA": _slice(series["dea"], start_index),
            "OSC": _slice(series["osc"], start_index),
            "K": _slice(series["k"], start_index),
            "D": _slice(series["d"], start_index),
        },
        index=index,
    )

    buy_markers = np.full(len(df), np.nan)
    sell_markers = np.full(len(df), np.nan)
    visible_events = [event for event in events if event["date"] in visible_dates]

    for event in visible_events:
        event_index = df.index.get_loc(pd.Timestamp(event["date"]))
        if event["type"] == "buy":
            buy_markers[event_index] = df["Low"].iloc[event_index] * 0.985
        else:
            sell_markers[event_index] = df["High"].iloc[event_index] * 1.015

    addplots = [
        mpf.make_addplot(df["MA5"], color="#f6c85f", width=1.2),
        mpf.make_addplot(df["MA10"], color="#66d9ef", width=1.1),
        mpf.make_addplot(df["MA20"], color="#d26cff", width=1.1),
        mpf.make_addplot(df["MA60"], color="#f2f2f2", width=1.0),
        mpf.make_addplot(df["MA120"], color="#ff9f43", width=1.0),
        mpf.make_addplot(df["DIF"], panel=2, color="#f6c85f", width=1.1),
        mpf.make_addplot(df["DEA"], panel=2, color="#58c4ff", width=1.1),
        mpf.make_addplot(df["OSC"], panel=2, type="bar", color=_bar_colors(df["OSC"])),
        mpf.make_addplot(df["K"], panel=3, color="#f6c85f", width=1.0),
        mpf.make_addplot(df["D"], panel=3, color="#58c4ff", width=1.0),
        mpf.make_addplot(pd.Series(80, index=df.index), panel=3, color="#9aa4b2", width=0.8, linestyle="--"),
        mpf.make_addplot(pd.Series(20, index=df.index), panel=3, color="#9aa4b2", width=0.8, linestyle="--"),
    ]

    if np.isfinite(buy_markers).any():
        addplots.append(mpf.make_addplot(buy_markers, type="scatter", marker="^", color="#63e6be", markersize=110))
    if np.isfinite(sell_markers).any():
        addplots.append(mpf.make_addplot(sell_markers, type="scatter", marker="v", color="#ff7a7a", markersize=110))

    style = mpf.make_mpf_style(
        base_mpf_style="nightclouds",
        marketcolors=mpf.make_marketcolors(
            up="#ff4d4f",
            down="#2ecc71",
            edge={"up": "#ff4d4f", "down": "#2ecc71"},
            wick={"up": "#ff4d4f", "down": "#2ecc71"},
            volume={"up": "#ff4d4f", "down": "#2ecc71"},
        ),
        figcolor="#07111c",
        facecolor="#07111c",
        gridcolor="#21364b",
        y_on_right=True,
    )

    fig, axes = mpf.plot(
        df,
        type="candle",
        volume=True,
        addplot=addplots,
        panel_ratios=(5, 1.6, 2, 2),
        style=style,
        figsize=(15, 10),
        datetime_format="%m/%d",
        tight_layout=True,
        returnfig=True,
    )

    main_ax = axes[0]
    title = f"{summary['symbol']} {summary['name']} | {summary['decision']['label']} | {summary['score']['total']}/10"
    main_ax.set_title(title, fontproperties=_FONT_PROP)

    for event in visible_events[-6:]:
        event_date = pd.Timestamp(event["date"])
        row = df.loc[event_date]
        if event["type"] == "buy":
            xy = (event_date, row["Low"] * 0.985)
            xytext = (event_date, row["Low"] * 0.955)
            color = "#63e6be"
            label = f"買進\n{_short_reason(event['reason'])}"
        else:
            xy = (event_date, row["High"] * 1.015)
            xytext = (event_date, row["High"] * 1.055)
            color = "#ff7a7a"
            label = f"賣出\n{_short_reason(event['reason'])}"

        main_ax.annotate(
            label,
            xy=xy,
            xytext=xytext,
            color=color,
            fontsize=8,
            ha="center",
            fontproperties=_FONT_PROP,
            arrowprops={"arrowstyle": "->", "color": color, "lw": 0.8},
            bbox={"boxstyle": "round,pad=0.2", "fc": "#0f2236", "ec": color, "alpha": 0.85},
        )

    latest_note = (
        f"策略摘要：{summary['signalSummary']}\n"
        f"操作建議：{summary['decision']['action']}\n"
        f"出場訊號：{_join_or_dash(summary['exitAnalysis']['activeSignals'])}\n"
        f"警示提醒：{_join_or_dash(summary['exitAnalysis']['activeWarnings'])}"
    )
    main_ax.text(
        0.01,
        0.98,
        latest_note,
        transform=main_ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        color="#eef5ff",
        fontproperties=_FONT_PROP,
        bbox={"boxstyle": "round,pad=0.35", "fc": "#102338", "ec": "#2a4661", "alpha": 0.92},
    )

    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def _slice(values: list, start_index: int) -> list[float]:
    return [np.nan if value is None else float(value) for value in values[start_index:]]


def _bar_colors(series: pd.Series) -> list[str]:
    return ["#ff6b6b" if value >= 0 else "#2ecc71" for value in series]


def _short_reason(reason: str) -> str:
    return reason if len(reason) <= 14 else f"{reason[:14]}..."


def _join_or_dash(values: list[str]) -> str:
    return "、".join(values) if values else "無"
