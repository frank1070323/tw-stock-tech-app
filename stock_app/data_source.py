from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .theme_registry import SPECIAL_STOCK_PROFILES


class StockDataError(Exception):
    pass


@dataclass(frozen=True)
class DailyBar:
    trading_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume_lots: float


@dataclass(frozen=True)
class StockHistory:
    symbol: str
    name: str
    market: str
    latest_date: date
    bars: list[DailyBar]


@dataclass(frozen=True)
class ResolvedSymbol:
    symbol: str
    market: str | None = None


class OfficialStockDataSource:
    TWSE_ENDPOINT = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    TPEX_ENDPOINT = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
    LISTED_BASIC = "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"
    OTC_BASIC = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0 Safari/537.36"

    def __init__(self, months_to_scan: int = 12):
        self.months_to_scan = months_to_scan
        self._csv_cache: dict[str, list[dict]] = {}
        self._alias_map = self._build_special_alias_map()

    def get_history(self, query: str) -> StockHistory:
        resolved = self.resolve_symbol(query)

        market_order = [resolved.market] if resolved.market else []
        market_order.extend(market for market in ["上市", "上櫃"] if market not in market_order)

        for market in market_order:
            history = self._try_market(resolved.symbol, market)
            if history:
                return history

        raise StockDataError("查不到這檔股票，請輸入代號或公司名稱。")

    def resolve_symbol(self, query: str) -> ResolvedSymbol:
        clean_query = (query or "").strip()
        if not clean_query:
            raise StockDataError("請輸入股票代號或公司名稱。")

        if clean_query.isdigit():
            return ResolvedSymbol(symbol=clean_query)

        normalized = self._normalize_query(clean_query)
        if normalized in self._alias_map:
            return self._alias_map[normalized]

        rows = self._load_company_lookup_rows()
        exact_matches = [row for row in rows if self._normalize_query(row["name"]) == normalized]
        if len(exact_matches) == 1:
            return ResolvedSymbol(symbol=exact_matches[0]["symbol"], market=exact_matches[0]["market"])

        partial_matches = [row for row in rows if normalized in self._normalize_query(row["name"])]
        unique_symbols = {(row["symbol"], row["market"]) for row in partial_matches}
        if len(unique_symbols) == 1:
            symbol, market = next(iter(unique_symbols))
            return ResolvedSymbol(symbol=symbol, market=market)

        raise StockDataError("查不到對應股票，請輸入股票代號、公司中文名，或像 AES-KY 這樣的英文名稱。")

    def _try_market(self, symbol: str, market: str) -> StockHistory | None:
        bars: list[DailyBar] = []
        stock_name = ""
        network_errors: list[str] = []

        for month in self._iter_recent_months():
            try:
                if market == "上市":
                    month_name, month_bars = self._fetch_twse_month(symbol, month.year, month.month)
                else:
                    month_name, month_bars = self._fetch_tpex_month(symbol, month.year, month.month)
            except (HTTPError, URLError, TimeoutError) as exc:
                network_errors.append(str(exc))
                continue

            if month_name and not stock_name:
                stock_name = month_name
            bars.extend(month_bars)

        if bars:
            unique_bars = self._dedupe_bars(bars)
            latest_date = unique_bars[-1].trading_date
            return StockHistory(
                symbol=symbol,
                name=stock_name or symbol,
                market=market,
                latest_date=latest_date,
                bars=unique_bars,
            )

        if network_errors:
            raise StockDataError("官方資料來源暫時不可用，請稍後再試。")

        return None

    def _fetch_twse_month(self, symbol: str, year: int, month: int) -> tuple[str, list[DailyBar]]:
        query = urlencode({"response": "json", "date": f"{year}{month:02d}01", "stockNo": symbol})
        payload = self._get_json(f"{self.TWSE_ENDPOINT}?{query}")
        if payload.get("stat") != "OK":
            return "", []

        title = payload.get("title", "")
        name = self._parse_twse_name(title, symbol)
        bars = []
        for row in payload.get("data", []):
            if len(row) < 7:
                continue
            parsed = self._build_bar(
                trading_date=row[0],
                open_price=row[3],
                high_price=row[4],
                low_price=row[5],
                close_price=row[6],
                volume_value=row[1],
                volume_divisor=1000.0,
            )
            if parsed:
                bars.append(parsed)
        return name, bars

    def _fetch_tpex_month(self, symbol: str, year: int, month: int) -> tuple[str, list[DailyBar]]:
        query = urlencode({"date": f"{year}/{month:02d}/01", "code": symbol})
        payload = self._get_json(f"{self.TPEX_ENDPOINT}?{query}")
        if payload.get("stat") != "ok":
            return "", []

        name = payload.get("name") or self._parse_tpex_name(payload, symbol)
        tables = payload.get("tables") or []
        if not tables:
            return name, []

        bars = []
        for row in tables[0].get("data", []):
            if len(row) < 7:
                continue
            parsed = self._build_bar(
                trading_date=row[0],
                open_price=row[3],
                high_price=row[4],
                low_price=row[5],
                close_price=row[6],
                volume_value=row[1],
                volume_divisor=1.0,
            )
            if parsed:
                bars.append(parsed)
        return name, bars

    def _build_bar(
        self,
        trading_date: str,
        open_price: str,
        high_price: str,
        low_price: str,
        close_price: str,
        volume_value: str,
        volume_divisor: float,
    ) -> DailyBar | None:
        try:
            parsed_open = self._to_float(open_price)
            parsed_high = self._to_float(high_price)
            parsed_low = self._to_float(low_price)
            parsed_close = self._to_float(close_price)
            parsed_volume = self._to_float(volume_value) / volume_divisor
            parsed_date = self._parse_roc_date(trading_date)
        except ValueError:
            return None

        return DailyBar(
            trading_date=parsed_date,
            open_price=parsed_open,
            high_price=parsed_high,
            low_price=parsed_low,
            close_price=parsed_close,
            volume_lots=parsed_volume,
        )

    def _get_json(self, url: str) -> dict:
        request = Request(url, headers={"User-Agent": self.USER_AGENT})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def _iter_recent_months(self) -> Iterable[date]:
        current = date.today().replace(day=1)
        year = current.year
        month = current.month

        for _ in range(self.months_to_scan):
            yield date(year, month, 1)
            month -= 1
            if month == 0:
                month = 12
                year -= 1

    def _dedupe_bars(self, bars: list[DailyBar]) -> list[DailyBar]:
        seen = {}
        for bar in sorted(bars, key=lambda item: item.trading_date):
            seen[bar.trading_date] = bar
        return list(seen.values())

    def _to_float(self, value: str) -> float:
        cleaned = value.replace(",", "").strip()
        if cleaned in {"", "--", "---"}:
            raise ValueError("missing numeric value")
        return float(cleaned)

    def _parse_roc_date(self, value: str) -> date:
        parts = value.split("/")
        if len(parts) != 3:
            raise ValueError("invalid ROC date")
        year, month, day = (int(part) for part in parts)
        return date(year + 1911, month, day)

    def _parse_twse_name(self, title: str, symbol: str) -> str:
        normalized = " ".join(title.split())
        match = re.search(rf"{re.escape(symbol)}\s+(.+?)\s+日成交資訊", normalized)
        return match.group(1).strip() if match else symbol

    def _parse_tpex_name(self, payload: dict, symbol: str) -> str:
        tables = payload.get("tables") or []
        if not tables:
            return symbol
        subtitle = tables[0].get("subtitle", "")
        normalized = " ".join(subtitle.split())
        match = re.search(rf"{re.escape(symbol)}\s+(.+?)\s+\d{{3}}/\d{{2}}", normalized)
        return match.group(1).strip() if match else symbol

    def _build_special_alias_map(self) -> dict[str, ResolvedSymbol]:
        mapping: dict[str, ResolvedSymbol] = {}
        for symbol, profile in SPECIAL_STOCK_PROFILES.items():
            mapping[self._normalize_query(symbol)] = ResolvedSymbol(symbol=symbol)
            mapping[self._normalize_query(profile["name"])] = ResolvedSymbol(symbol=symbol)
            for alias in profile.get("aliases", []):
                mapping[self._normalize_query(alias)] = ResolvedSymbol(symbol=symbol)
        return mapping

    def _load_company_lookup_rows(self) -> list[dict]:
        rows: list[dict] = []
        for market, url in [("上市", self.LISTED_BASIC), ("上櫃", self.OTC_BASIC)]:
            for row in self._load_csv_records(url):
                symbol = (row.get("公司代號") or "").strip()
                name = (row.get("公司名稱") or row.get("公司簡稱") or "").strip()
                if symbol and name:
                    rows.append({"symbol": symbol, "name": name, "market": market})
        return rows

    def _load_csv_records(self, url: str) -> list[dict]:
        if url in self._csv_cache:
            return self._csv_cache[url]
        request = Request(url, headers={"User-Agent": self.USER_AGENT})
        with urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8-sig", errors="ignore")

        rows = list(csv.reader(io.StringIO(text)))
        rows = [row for row in rows if row and any(cell.strip() for cell in row)]
        if not rows:
            self._csv_cache[url] = []
            return []

        header_index = 0
        for index, row in enumerate(rows):
            if "公司代號" in row or "股票代號" in row:
                header_index = index
                break

        headers = [cell.strip() for cell in rows[header_index]]
        records: list[dict] = []
        for row in rows[header_index + 1 :]:
            if len(row) != len(headers):
                continue
            records.append({headers[i]: row[i].strip() for i in range(len(headers))})

        self._csv_cache[url] = records
        return records

    def _normalize_query(self, value: str) -> str:
        return re.sub(r"[\s\-_]+", "", value or "").upper()
