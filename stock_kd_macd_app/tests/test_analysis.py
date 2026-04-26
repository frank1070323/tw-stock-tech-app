from datetime import date, timedelta
import unittest

from stock_app.analysis import StockAnalyzer
from stock_app.data_source import DailyBar, StockHistory


class FakeDataSource:
    def __init__(self, history):
        self.history = history

    def get_history(self, symbol):
        return self.history


class AnalysisTests(unittest.TestCase):
    def test_scoring_engine_builds_weighted_result_and_risk_plan(self):
        bars = []
        start = date(2025, 10, 1)
        closes = []
        for index in range(100):
            closes.append(60 + index * 0.35)
        closes += [94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84, 83, 82, 81, 80]
        closes += [81, 82, 83, 84, 85, 86, 88, 90, 93, 97, 102, 108, 112, 116, 120]
        volumes = [1500 + index * 5 for index in range(len(closes))]
        volumes[-5:] = [1800, 1900, 2100, 2600, 5200]

        for index, close_price in enumerate(closes):
            bars.append(
                DailyBar(
                    trading_date=start + timedelta(days=index),
                    open_price=close_price - 0.8,
                    high_price=close_price + 1.2,
                    low_price=close_price - 1.5,
                    close_price=close_price,
                    volume_lots=volumes[index],
                )
            )

        history = StockHistory(
            symbol="9999",
            name="測試股",
            market="上市",
            latest_date=bars[-1].trading_date,
            bars=bars,
        )

        result = StockAnalyzer(FakeDataSource(history)).analyze("9999", target_price=135, stop_price=112)

        self.assertEqual(result["decision"]["label"], "觀望過濾")
        self.assertEqual(result["score"]["total"], 6)
        self.assertTrue(result["movingAverageAnalysis"]["pass"])
        self.assertTrue(result["volumeAnalysis"]["pass"])
        self.assertEqual(result["score"]["ma"], 3)
        self.assertEqual(result["score"]["volume"], 3)
        self.assertIn("supportResistance", result)
        self.assertIn("riskPlan", result)
        self.assertTrue(result["riskPlan"]["valid"])
        self.assertAlmostEqual(result["riskPlan"]["rrRatio"], 1.88, places=2)


if __name__ == "__main__":
    unittest.main()
