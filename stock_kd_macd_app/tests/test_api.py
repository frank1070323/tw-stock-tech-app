import unittest

from stock_app import create_app
from stock_app.data_source import StockDataError


class StubAnalyzer:
    def analyze(self, symbol, target_price=None, stop_price=None):
        if symbol == "0000":
            raise StockDataError("查不到股票代號")
        return {
            "symbol": "6442",
            "name": "光聖",
            "market": "上市",
            "dataDate": "2026-04-24",
            "latestClose": 1880.0,
            "latestVolumeLots": 1925.0,
            "movingAverages": {"ma5": 2170.0, "ma10": 2147.5, "ma20": 2120.5, "ma60": 1899.58, "ma120": 1529.23},
            "movingAverageAnalysis": {
                "priceAboveMa5": False,
                "bullishStack": True,
                "ma60Direction": "上行",
                "ma120Direction": "上行",
                "longTrendSupport": True,
                "pass": False,
            },
            "volumeAverages": {"vma5": 2300.0, "vma20": 2500.0},
            "volumeAnalysis": {"ratioToVma5": 0.84, "aboveVma20": False, "burst": False, "pass": False},
            "k": 28.41,
            "d": 42.07,
            "dif": 47.02,
            "dea": 76.40,
            "osc": -29.38,
            "kdDirection": "下行",
            "kdCurve": "向上彎曲",
            "kdSignal": "無",
            "kdLowZone": True,
            "kdPass": False,
            "macdDirection": "下行",
            "macdCurve": "向下彎曲",
            "macdZeroAxis": "零上",
            "oscDirection": "零下",
            "oscFlipPositive": False,
            "negativeBarsShortening": False,
            "macdGoldCross": False,
            "zeroAxisGoldCross": False,
            "macdPass": False,
            "score": {"ma": 0, "kd": 0, "macd": 0, "volume": 0, "total": 0},
            "decision": {"label": "觀望過濾", "action": "先觀察，不要因為單一指標上彎就急著追。"},
            "dashboard": {"tone": "danger", "label": "觀望為主", "headline": "條件不夠整齊，先別急著追", "scoreHint": "0/10"},
            "signalSummary": "策略分數 0/10，目前判定為「觀望過濾」。",
            "entryNarrative": "目前偏觀望。",
            "supportResistance": {
                "atr14": 66.4,
                "atrStopLoss": 1747.2,
                "suggestedStopLoss": 1820.0,
                "quarterHighResistance": 2540.0,
                "quarterLowSupport": 1680.0,
                "maxVolumeSupport": 1820.0,
                "keyBullBarSupport": 1865.0,
                "ma20Support": 2120.5,
            },
            "riskPlan": {
                "targetPrice": target_price or 2540.0,
                "stopPrice": stop_price or 1820.0,
                "riskAmount": 60.0,
                "rewardAmount": 660.0,
                "rrRatio": 11.0,
                "valid": True,
                "note": "這筆交易的風險報酬比達標，條件算健康。",
            },
            "backtest": {
                "closedTrades": 5,
                "winningTrades": 3,
                "winRate": 60.0,
                "avgReturn": 4.5,
                "bestTrade": 12.0,
                "worstTrade": -5.0,
                "note": "這裡是用目前策略規則回放歷史訊號。",
            },
            "exitAnalysis": {
                "holdingPosition": False,
                "activeSignals": [],
                "activeWarnings": [],
                "lastTrade": None,
                "recentEvents": [],
                "rules": {
                    "priceTrigger": 2170.0,
                    "kdTrigger": "K 在 80 以上且跌破 D，或高檔開始向下彎曲",
                    "volumeTrigger": "創高但量縮，或量能跌回 VMA5 下方",
                    "trailingStopTrigger": "自波段高點回落 8%",
                    "ma20Trigger": "跌破 MA20 且連續 3 日站不回",
                },
            },
            "companyProfile": {
                "displayName": "光聖 (6442)",
                "industry": "通信網路業",
                "coreBusiness": "光通訊主被動元件",
                "themes": ["#矽光子CPO"],
                "peerCodes": ["3363"],
                "sectorName": "矽光子 / 光通訊",
            },
            "peerComparison": [],
            "chipAnalysis": {
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
                "narrative": "資料不足",
            },
            "fundamentals": {
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
                "narrative": "資料不足",
            },
            "sentiment": {
                "available": False,
                "newsCount7d": None,
                "label": "資料不足",
                "items": [],
                "narrative": "資料不足",
            },
            "statusTags": [{"label": "#持股監控中", "tone": "neutral"}],
        }

    def render_chart(self, symbol):
        if symbol == "0000":
            raise StockDataError("查不到股票代號")
        return b"fakepng"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "ANALYZER": StubAnalyzer()})
        self.client = self.app.test_client()

    def test_requires_symbol(self):
        response = self.client.get("/api/analyze")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "請輸入股票代號或公司名稱。")

    def test_returns_analysis_payload(self):
        response = self.client.get("/api/analyze?symbol=AES-KY&target_price=210&stop_price=188")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["symbol"], "6442")
        self.assertEqual(payload["market"], "上市")
        self.assertEqual(payload["movingAverages"]["ma5"], 2170.0)
        self.assertEqual(payload["riskPlan"]["targetPrice"], 210.0)
        self.assertEqual(payload["riskPlan"]["stopPrice"], 188.0)
        self.assertIn("supportResistance", payload)
        self.assertIn("backtest", payload)

    def test_returns_domain_error(self):
        response = self.client.get("/api/analyze?symbol=0000")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "查不到股票代號")

    def test_chart_endpoint_returns_png(self):
        response = self.client.get("/api/chart?symbol=6442")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.data, b"fakepng")


if __name__ == "__main__":
    unittest.main()
