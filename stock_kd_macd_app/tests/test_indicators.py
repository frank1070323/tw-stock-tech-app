import unittest

from stock_app.indicators import (
    calculate_atr,
    calculate_kd,
    calculate_macd,
    calculate_sma,
    classify_curve,
    classify_direction,
    classify_zero_axis,
    detect_kd_signal,
)


class IndicatorTests(unittest.TestCase):
    def setUp(self):
        self.closes = [
            100.0, 101.2, 100.8, 102.5, 103.1, 102.7, 104.2, 105.4, 104.8, 106.1,
            107.0, 108.4, 107.6, 109.3, 110.5, 109.9, 111.8, 112.6, 113.4, 112.9,
            114.2, 115.1, 114.6, 116.8, 117.3, 116.2, 118.4, 119.8, 120.4, 121.7,
        ]
        self.highs = [price + 1.2 for price in self.closes]
        self.lows = [price - 1.4 for price in self.closes]

    def test_kd_is_stable_for_fixed_sample(self):
        _, k_values, d_values = calculate_kd(self.closes, self.highs, self.lows)
        self.assertEqual(len(k_values), len(self.closes))
        self.assertEqual(len(d_values), len(self.closes))
        self.assertAlmostEqual(k_values[-1], 85.41, places=2)
        self.assertAlmostEqual(d_values[-1], 83.87, places=2)

    def test_macd_is_stable_for_fixed_sample(self):
        dif_values, dea_values, osc_values = calculate_macd(self.closes)
        self.assertEqual(len(dif_values), len(self.closes))
        self.assertEqual(len(dea_values), len(self.closes))
        self.assertEqual(len(osc_values), len(self.closes))
        self.assertAlmostEqual(dif_values[-1], 4.17, places=2)
        self.assertAlmostEqual(dea_values[-1], 3.69, places=2)
        self.assertAlmostEqual(osc_values[-1], 0.48, places=2)

    def test_sma_and_atr_are_stable_for_fixed_sample(self):
        ma5 = calculate_sma(self.closes, 5)
        ma10 = calculate_sma(self.closes, 10)
        atr14 = calculate_atr(self.highs, self.lows, self.closes, period=14)
        self.assertIsNone(ma5[3])
        self.assertAlmostEqual(ma5[-1], 119.3, places=2)
        self.assertAlmostEqual(ma10[-1], 117.45, places=2)
        self.assertAlmostEqual(atr14[-1], 2.75, places=2)

    def test_kd_signal_detection(self):
        self.assertEqual(detect_kd_signal([20.0, 45.0], [30.0, 35.0]), "黃金交叉")
        self.assertEqual(detect_kd_signal([50.0, 30.0], [40.0, 35.0]), "死亡交叉")
        self.assertEqual(detect_kd_signal([40.0, 42.0], [38.0, 39.0]), "無")

    def test_macd_status_classification(self):
        self.assertEqual(classify_direction([1.0, 2.0, 3.2], min_threshold=0.05), "上行")
        self.assertEqual(classify_direction([3.2, 2.0, 1.0], min_threshold=0.05), "下行")
        self.assertEqual(classify_curve([1.0, 2.0, 3.5], min_threshold=0.05), "向上彎曲")
        self.assertEqual(classify_curve([3.5, 2.5, 0.5], min_threshold=0.05), "向下彎曲")
        self.assertEqual(classify_zero_axis(1.2, min_threshold=0.05), "零上")
        self.assertEqual(classify_zero_axis(-1.2, min_threshold=0.05), "零下")
        self.assertEqual(classify_zero_axis(0.01, min_threshold=0.05), "貼近零軸")


if __name__ == "__main__":
    unittest.main()
