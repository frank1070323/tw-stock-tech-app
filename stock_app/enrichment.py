from __future__ import annotations

import csv
import io
import json
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .theme_registry import INDUSTRY_CODE_MAP, INDUSTRY_THEME_MAP, SPECIAL_STOCK_PROFILES, THEME_CATALOG


class StockEnrichmentService:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0 Safari/537.36"

    LISTED_BASIC = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
    OTC_BASIC = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
    LISTED_REVENUE = "https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv"
    OTC_REVENUE = "https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv"
    LISTED_PE = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?response=open_data"
    OTC_PE = "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=csv"
    TWSE_T86 = "https://www.twse.com.tw/rwd/zh/fund/T86"
    TPEX_T86 = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"

    def __init__(self, data_source, network_enabled: bool = False):
        self.data_source = data_source
        self.network_enabled = network_enabled
        self._text_cache: dict[str, str] = {}
        self._csv_cache: dict[str, list[dict]] = {}
        self._json_cache: dict[str, dict] = {}

    def build_intelligence(self, history, snapshot: dict, exit_analysis: dict) -> dict:
        company_profile = self._build_company_profile(history)
        peer_comparison = self._build_peer_comparison(history.symbol, company_profile["peerCodes"])
        chip_analysis = self._build_chip_analysis(history, snapshot)
        fundamentals = self._build_fundamentals(history, company_profile, snapshot, exit_analysis)
        sentiment = self._build_sentiment(company_profile)
        return {
            "companyProfile": company_profile,
            "peerComparison": peer_comparison,
            "chipAnalysis": chip_analysis,
            "fundamentals": fundamentals,
            "sentiment": sentiment,
        }

    def _build_company_profile(self, history) -> dict:
        special = SPECIAL_STOCK_PROFILES.get(history.symbol, {})
        basic = self._fetch_company_basic(history.market, history.symbol) if self.network_enabled else {}
        revenue = self._fetch_revenue_row(history.market, history.symbol) if self.network_enabled else {}

        name = (
            special.get("name")
            or self._get_first(basic, ["公司名稱", "公司簡稱"])
            or self._get_first(revenue, ["公司名稱"])
            or history.name
        )
        industry = self._normalize_industry(
            self._get_first(revenue, ["產業別", "產業類別"])
            or self._get_first(basic, ["產業別", "產業類別", "公司別"])
            or history.market
        )
        core_business = special.get("core_business") or self._compose_core_business(name, industry)
        inferred = self._infer_theme_profile(history.symbol, name, core_business, industry)

        return {
            "displayName": f"{name} ({history.symbol})",
            "industry": industry,
            "coreBusiness": core_business,
            "themes": inferred["themes"],
            "peerCodes": inferred["peerCodes"],
            "sectorName": inferred["sectorName"],
            "market": history.market,
        }

    def _build_peer_comparison(self, symbol: str, peer_codes: list[str]) -> list[dict]:
        peers: list[dict] = []
        for peer_code in peer_codes[:6]:
            try:
                peer_history = self.data_source.get_history(peer_code)
            except Exception:
                continue
            if len(peer_history.bars) < 2:
                continue
            latest_close = peer_history.bars[-1].close_price
            previous_close = peer_history.bars[-2].close_price
            change_percent = ((latest_close - previous_close) / previous_close) * 100 if previous_close else 0.0
            peers.append(
                {
                    "symbol": peer_code,
                    "name": SPECIAL_STOCK_PROFILES.get(peer_code, {}).get("name") or peer_history.name,
                    "market": peer_history.market,
                    "changePercent": round(change_percent, 2),
                    "isCurrent": peer_code == symbol,
                }
            )

        peers.sort(key=lambda item: item["changePercent"], reverse=True)
        for index, item in enumerate(peers, start=1):
            item["rank"] = index
            item["role"] = "領漲" if index == 1 else ("落後補漲" if index == len(peers) else "同族群")
        return peers

    def _build_chip_analysis(self, history, snapshot: dict) -> dict:
        default_payload = {
            "available": False,
            "latest": None,
            "foreignBuyDays": 0,
            "trustBuyDays": 0,
            "dealerBuyDays": 0,
            "concentration": {
                "available": False,
                "days5": None,
                "days10": None,
                "days20": None,
                "label": "資料不足",
                "note": "目前沒有足夠法人資料。",
            },
            "tags": [],
            "narrative": "目前沒有足夠法人資料，先把籌碼當輔助判讀。",
        }
        if not self.network_enabled:
            return default_payload

        rows = []
        for bar in reversed(history.bars[-30:]):
            row = self._fetch_institution_row(history.market, history.symbol, bar.trading_date)
            if row:
                rows.append(row)
            if len(rows) >= 20:
                break

        if not rows:
            return default_payload

        latest = rows[0]
        foreign_days = self._count_positive_streak(rows, "foreign_net")
        trust_days = self._count_positive_streak(rows, "trust_net")
        dealer_days = self._count_positive_streak(rows, "dealer_net")
        concentration = self._build_chip_concentration(rows)

        tags = []
        if foreign_days >= 3:
            tags.append("#外資連買")
        elif latest["foreign_net"] > 0:
            tags.append("#外資偏多")
        if trust_days >= 3:
            tags.append("#投信連買")
        elif latest["trust_net"] > 0:
            tags.append("#投信偏多")
        if dealer_days >= 3:
            tags.append("#自營連買")
        elif latest["dealer_net"] > 0:
            tags.append("#自營偏多")
        if concentration["label"] in {"集中偏多", "溫和偏多"}:
            tags.append("#法人集中")

        if snapshot["score"]["total"] >= 7 and trust_days >= 3:
            narrative = "技術面偏強，投信也有持續站在買方，籌碼面算加分。"
        elif concentration["label"] == "集中偏多":
            narrative = "近 5 / 10 / 20 日三大法人累積淨買超都偏多，籌碼有慢慢集中。"
        elif concentration["label"] == "集中偏空":
            narrative = "近幾個觀察週期都偏向賣超，資金還沒有明顯回流。"
        elif latest["foreign_net"] < 0 and latest["trust_net"] < 0 and latest["dealer_net"] < 0:
            narrative = "三大法人最新一日同步偏空，這塊暫時別太樂觀。"
        else:
            narrative = "法人沒有完全同向，籌碼面先當輔助判讀。"

        return {
            "available": True,
            "latest": latest,
            "foreignBuyDays": foreign_days,
            "trustBuyDays": trust_days,
            "dealerBuyDays": dealer_days,
            "concentration": concentration,
            "tags": tags,
            "narrative": narrative,
        }

    def _build_fundamentals(self, history, company_profile: dict, snapshot: dict, exit_analysis: dict) -> dict:
        default_payload = {
            "available": False,
            "pe": None,
            "dividendYield": None,
            "pbRatio": None,
            "pePosition": "資料不足",
            "revenueYoY": None,
            "revenueMoM": None,
            "revenueMonth": None,
            "currentRevenue": None,
            "earningsOutlook": "資料不足",
            "narrative": "目前沒有抓到足夠基本面資料，先把技術面當主判斷。",
            "industry": company_profile["industry"],
        }
        if not self.network_enabled:
            return default_payload

        pe_row = self._fetch_pe_row(history.market, history.symbol)
        revenue_row = self._fetch_revenue_row(history.market, history.symbol)
        if not pe_row and not revenue_row:
            return default_payload

        pe = self._to_float(self._get_first(pe_row, ["本益比", "PER", "PEratio"]))
        dividend_yield = self._to_float(self._get_first(pe_row, ["殖利率(%)", "DividendYield"]))
        pb_ratio = self._to_float(self._get_first(pe_row, ["股價淨值比", "PBRatio"]))
        revenue_yoy = self._to_float(
            self._get_first(
                revenue_row,
                ["當月營收-去年同月增減(%)", "營業收入-去年同月增減(%)", "去年同月增減(%)"],
            )
        )
        revenue_mom = self._to_float(
            self._get_first(
                revenue_row,
                ["當月營收-上月比較增減(%)", "營業收入-上月比較增減(%)", "上月比較增減(%)"],
            )
        )
        current_revenue = self._to_float(
            self._get_first(
                revenue_row,
                ["當月營收", "當月營收-新台幣千元", "營業收入-當月營收", "營業收入-當月營收(千元)"],
            )
        )
        revenue_month = self._get_first(revenue_row, ["資料年月", "出表日期"])
        pe_position = self._classify_pe_position(pe)
        earnings_outlook = self._classify_earnings_outlook(revenue_yoy, revenue_mom)

        messages = []
        if pe is not None:
            messages.append(f"本益比約 {pe:.2f}，目前屬於「{pe_position}」位階。")
        else:
            messages.append("本益比資料暫時抓不到。")

        if revenue_yoy is not None:
            messages.append(f"最新月營收年增 {revenue_yoy:.2f}%。")
        else:
            messages.append("最新月營收年增資料不足。")

        if pe_position == "昂貴" and any(signal.startswith("KD 高檔") for signal in exit_analysis["activeSignals"]):
            messages.append("位階偏高又出現高檔轉弱訊號，減碼會比較穩。")
        elif revenue_yoy is not None and revenue_yoy < 0 and not snapshot["movingAverageAnalysis"]["priceAboveMa5"]:
            messages.append("營收動能轉弱又跌破五日線，操作上要保守。")
        else:
            messages.append("基本面先當過濾條件，仍要和技術面一起看。")

        return {
            "available": True,
            "pe": pe,
            "dividendYield": dividend_yield,
            "pbRatio": pb_ratio,
            "pePosition": pe_position,
            "revenueYoY": revenue_yoy,
            "revenueMoM": revenue_mom,
            "revenueMonth": revenue_month,
            "currentRevenue": current_revenue,
            "earningsOutlook": earnings_outlook,
            "narrative": " ".join(messages),
            "industry": company_profile["industry"],
        }

    def _build_sentiment(self, company_profile: dict) -> dict:
        default_payload = {
            "available": False,
            "newsCount7d": None,
            "label": "資料不足",
            "items": [],
            "narrative": "目前沒有足夠新聞資料，情緒面先不納入主判斷。",
        }
        if not self.network_enabled:
            return default_payload

        try:
            items = self._fetch_news_items(company_profile["displayName"].split(" (")[0], company_profile["themes"])
        except Exception:
            return default_payload

        count = len(items)
        if count >= 10:
            label = "熱度偏高"
            narrative = "近一週討論度偏高，容易有追價與震盪，要更守紀律。"
        elif count >= 4:
            label = "熱度中等"
            narrative = "市場有持續關注，但還沒有到過熱。"
        else:
            label = "熱度偏低"
            narrative = "目前討論熱度不高，情緒面干擾較小。"

        return {
            "available": True,
            "newsCount7d": count,
            "label": label,
            "items": items[:5],
            "narrative": narrative,
        }

    def _fetch_company_basic(self, market: str, symbol: str) -> dict:
        url = self.LISTED_BASIC if market == "上市" else self.OTC_BASIC
        rows = self._load_csv_records(url)
        return self._find_latest_by_symbol(rows, symbol)

    def _fetch_revenue_row(self, market: str, symbol: str) -> dict:
        url = self.LISTED_REVENUE if market == "上市" else self.OTC_REVENUE
        rows = self._load_csv_records(url)
        return self._find_latest_by_symbol(rows, symbol)

    def _fetch_pe_row(self, market: str, symbol: str) -> dict:
        url = self.LISTED_PE if market == "上市" else self.OTC_PE
        rows = self._load_csv_records(url)
        return self._find_latest_by_symbol(rows, symbol)

    def _fetch_institution_row(self, market: str, symbol: str, trading_date) -> dict | None:
        if market == "上市":
            query = urlencode({"date": trading_date.strftime("%Y%m%d"), "selectType": "ALLBUT0999", "response": "json"})
            payload = self._fetch_json(f"{self.TWSE_T86}?{query}")
            for row in payload.get("data", []):
                if row and str(row[0]).strip() == symbol:
                    return {
                        "date": trading_date.isoformat(),
                        "foreign_net": self._to_float(row[4]) or 0.0,
                        "trust_net": self._to_float(row[10]) or 0.0,
                        "dealer_net": (self._to_float(row[14]) or 0.0) + (self._to_float(row[17]) or 0.0),
                        "total_net": self._to_float(row[18]) or 0.0,
                    }
            return None

        roc_date = f"{trading_date.year - 1911}/{trading_date.month:02d}/{trading_date.day:02d}"
        query = urlencode({"l": "zh-tw", "o": "csv", "se": "EW", "s": "0,asc", "d": roc_date})
        rows = self._load_csv_records(f"{self.TPEX_T86}?{query}")
        row = self._find_latest_by_symbol(rows, symbol)
        if not row:
            return None

        return {
            "date": trading_date.isoformat(),
            "foreign_net": self._to_float(
                self._get_first(
                    row,
                    [
                        "外資及陸資(不含外資自營商)-買賣超股數",
                        "外資及陸資買賣超股數",
                        "外資及陸資淨買賣超股數",
                    ],
                )
            )
            or 0.0,
            "trust_net": self._to_float(self._get_first(row, ["投信-買賣超股數", "投信買賣超股數"])) or 0.0,
            "dealer_net": self._to_float(self._get_first(row, ["自營商-買賣超股數", "自營商買賣超股數"])) or 0.0,
            "total_net": self._to_float(self._get_first(row, ["三大法人買賣超股數合計", "三大法人買賣超股數"])) or 0.0,
        }

    def _fetch_news_items(self, company_name: str, themes: list[str]) -> list[dict]:
        query_terms = [company_name]
        query_terms.extend(tag.lstrip("#") for tag in themes[:2])
        query = " OR ".join(term for term in query_terms if term)
        url = f"{self.GOOGLE_NEWS_RSS}?q={quote(query)}+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        root = ElementTree.fromstring(self._fetch_text(url, encoding="utf-8"))
        items = []
        for item in root.findall(".//item"):
            title = item.findtext("title") or ""
            pub_date = item.findtext("pubDate") or ""
            try:
                published = parsedate_to_datetime(pub_date).isoformat()
            except Exception:
                published = ""
            items.append({"title": title, "publishedAt": published})
        return items

    def _infer_theme_profile(self, symbol: str, name: str, core_business: str, industry: str) -> dict:
        special = SPECIAL_STOCK_PROFILES.get(symbol)
        if special:
            return {
                "themes": special["themes"],
                "peerCodes": special.get("peer_codes", []),
                "sectorName": special.get("sector_name") or industry,
            }

        text = " ".join([name, core_business, industry]).lower()
        matched_themes = []
        matched_sectors = []
        for entry in THEME_CATALOG:
            if any(keyword.lower() in text for keyword in entry["keywords"]):
                matched_themes.append(entry["label"])
                matched_sectors.append(entry["sector_name"])

        if not matched_themes:
            matched_themes = INDUSTRY_THEME_MAP.get(industry, ["#題材待補"])
        sector_name = matched_sectors[0] if matched_sectors else industry
        return {"themes": matched_themes[:4], "peerCodes": [], "sectorName": sector_name}

    def _compose_core_business(self, name: str, industry: str) -> str:
        return f"{name} 目前先依官方產業別歸為「{industry}」，後續可再補更細的產品線描述。"

    def _normalize_industry(self, raw_value: str | None) -> str:
        if not raw_value:
            return "其他"
        value = str(raw_value).strip()
        if value in INDUSTRY_CODE_MAP:
            return INDUSTRY_CODE_MAP[value]
        if value.isdigit():
            return INDUSTRY_CODE_MAP.get(value.zfill(2), value)
        return value

    def _classify_pe_position(self, pe_value: float | None) -> str:
        if pe_value is None or pe_value <= 0:
            return "資料不足"
        if pe_value >= 35:
            return "昂貴"
        if pe_value <= 15:
            return "便宜"
        return "合理"

    def _classify_earnings_outlook(self, revenue_yoy: float | None, revenue_mom: float | None) -> str:
        if revenue_yoy is None and revenue_mom is None:
            return "資料不足"
        if (revenue_yoy or 0) > 20 and (revenue_mom or 0) > 0:
            return "營收動能偏強"
        if (revenue_yoy or 0) < 0 and (revenue_mom or 0) < 0:
            return "營收動能轉弱"
        return "營收動能中性"

    def _build_chip_concentration(self, rows: list[dict]) -> dict:
        def window_sum(size: int) -> float | None:
            sample = rows[:size]
            if len(sample) < min(size, 3):
                return None
            return round(sum(item.get("total_net", 0.0) for item in sample), 2)

        days5 = window_sum(5)
        days10 = window_sum(10)
        days20 = window_sum(20)
        available_values = [value for value in [days5, days10, days20] if value is not None]

        label = "資料不足"
        note = "目前近 5 / 10 / 20 日法人資料不足。"
        if available_values:
            positive_count = sum(1 for value in available_values if value > 0)
            negative_count = sum(1 for value in available_values if value < 0)
            if positive_count == len(available_values):
                label = "集中偏多" if (days5 or 0) > 0 and (days10 or 0) > 0 else "溫和偏多"
                note = "這裡先用三大法人近 5 / 10 / 20 日累積淨買超近似法人集中度。"
            elif negative_count == len(available_values):
                label = "集中偏空"
                note = "近幾個觀察週期都偏向賣超，資金沒有明顯回流。"
            else:
                label = "分歧"
                note = "不同時間窗的法人態度不一致，籌碼沒有完全同向。"

        return {
            "available": bool(available_values),
            "days5": days5,
            "days10": days10,
            "days20": days20,
            "label": label,
            "note": note,
        }

    def _count_positive_streak(self, rows: list[dict], key: str) -> int:
        streak = 0
        for row in rows:
            if row.get(key, 0) <= 0:
                break
            streak += 1
        return streak

    def _load_csv_records(self, url: str) -> list[dict]:
        if url in self._csv_cache:
            return self._csv_cache[url]

        encoding = "cp950" if "tpex.org.tw" in url and "o=csv" in url else "utf-8-sig"
        text = self._fetch_text(url, encoding=encoding)
        rows = list(csv.reader(io.StringIO(text)))
        rows = [row for row in rows if row and any(cell.strip() for cell in row)]
        if not rows:
            self._csv_cache[url] = []
            return []

        header_index = 0
        header_tokens = {"公司代號", "股票代號", "證券代號", "代號"}
        for index, row in enumerate(rows):
            if any(token in row for token in header_tokens):
                header_index = index
                break

        headers = [cell.strip() for cell in rows[header_index]]
        records = []
        for row in rows[header_index + 1 :]:
            if len(row) != len(headers):
                continue
            records.append({headers[i]: row[i].strip() for i in range(len(headers))})

        self._csv_cache[url] = records
        return records

    def _find_latest_by_symbol(self, rows: list[dict], symbol: str) -> dict:
        matched = [row for row in rows if self._extract_code(row) == symbol]
        if not matched:
            return {}
        matched.sort(key=self._sort_key_from_row, reverse=True)
        return matched[0]

    def _extract_code(self, row: dict) -> str:
        return (row.get("公司代號") or row.get("股票代號") or row.get("證券代號") or row.get("代號") or "").strip()

    def _sort_key_from_row(self, row: dict) -> tuple[int, str]:
        date_value = row.get("資料年月") or row.get("出表日期") or row.get("日期") or row.get("年/月") or ""
        normalized = "".join(character for character in str(date_value) if character.isdigit())
        numeric = int(normalized) if normalized else 0
        return numeric, json.dumps(row, ensure_ascii=False, sort_keys=True)

    def _fetch_json(self, url: str) -> dict:
        if url in self._json_cache:
            return self._json_cache[url]
        text = self._fetch_text(url, encoding="utf-8")
        payload = json.loads(text)
        self._json_cache[url] = payload
        return payload

    def _fetch_text(self, url: str, encoding: str = "utf-8") -> str:
        if url in self._text_cache:
            return self._text_cache[url]
        request = Request(url, headers={"User-Agent": self.USER_AGENT})
        with urlopen(request, timeout=15) as response:
            raw = response.read()
        text = raw.decode(encoding, errors="ignore")
        self._text_cache[url] = text
        return text

    def _get_first(self, row: dict, keys: list[str]) -> str | None:
        for key in keys:
            value = row.get(key)
            if value not in {None, ""}:
                return str(value).strip()
        return None

    def _to_float(self, value) -> float | None:
        if value is None:
            return None
        cleaned = str(value).replace(",", "").replace("%", "").strip()
        if cleaned in {"", "--", "---", "N/A"}:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
