from __future__ import annotations

from typing import Iterable


def calculate_kd(
    closes: Iterable[float],
    highs: Iterable[float],
    lows: Iterable[float],
    period: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    close_list = list(closes)
    high_list = list(highs)
    low_list = list(lows)

    if not close_list or len(close_list) != len(high_list) or len(close_list) != len(low_list):
        raise ValueError("KD input lengths must match and not be empty.")

    rsv_values: list[float] = []
    k_values: list[float] = []
    d_values: list[float] = []

    previous_k = 50.0
    previous_d = 50.0

    for index in range(len(close_list)):
        start = max(0, index - period + 1)
        period_high = max(high_list[start : index + 1])
        period_low = min(low_list[start : index + 1])

        if period_high == period_low:
            rsv = 50.0
        else:
            rsv = ((close_list[index] - period_low) / (period_high - period_low)) * 100.0

        current_k = ((2.0 * previous_k) + rsv) / 3.0
        current_d = ((2.0 * previous_d) + current_k) / 3.0

        rsv_values.append(rsv)
        k_values.append(current_k)
        d_values.append(current_d)

        previous_k = current_k
        previous_d = current_d

    return rsv_values, k_values, d_values


def calculate_macd(
    closes: Iterable[float],
    short_period: int = 12,
    long_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    close_list = list(closes)
    if not close_list:
        raise ValueError("MACD input must not be empty.")

    ema_short = _ema(close_list, short_period)
    ema_long = _ema(close_list, long_period)
    dif_values = [short_value - long_value for short_value, long_value in zip(ema_short, ema_long)]
    dea_values = _ema(dif_values, signal_period)
    osc_values = [dif_value - dea_value for dif_value, dea_value in zip(dif_values, dea_values)]
    return dif_values, dea_values, osc_values


def calculate_sma(values: Iterable[float], period: int) -> list[float | None]:
    value_list = list(values)
    if not value_list:
        raise ValueError("SMA input must not be empty.")

    results: list[float | None] = []
    window_sum = 0.0

    for index, value in enumerate(value_list):
        window_sum += value
        if index >= period:
            window_sum -= value_list[index - period]
        if index + 1 < period:
            results.append(None)
        else:
            results.append(window_sum / period)

    return results


def calculate_atr(
    highs: Iterable[float],
    lows: Iterable[float],
    closes: Iterable[float],
    period: int = 14,
) -> list[float | None]:
    high_list = list(highs)
    low_list = list(lows)
    close_list = list(closes)

    if not high_list or len(high_list) != len(low_list) or len(high_list) != len(close_list):
        raise ValueError("ATR input lengths must match and not be empty.")

    true_ranges: list[float] = []
    for index, (high_value, low_value) in enumerate(zip(high_list, low_list)):
        if index == 0:
            true_range = high_value - low_value
        else:
            previous_close = close_list[index - 1]
            true_range = max(
                high_value - low_value,
                abs(high_value - previous_close),
                abs(low_value - previous_close),
            )
        true_ranges.append(true_range)

    return calculate_sma(true_ranges, period)


def detect_kd_signal(k_values: list[float], d_values: list[float]) -> str:
    if len(k_values) < 2 or len(d_values) < 2:
        return "無"

    previous_gap = k_values[-2] - d_values[-2]
    current_gap = k_values[-1] - d_values[-1]

    if previous_gap <= 0 and current_gap > 0:
        return "黃金交叉"
    if previous_gap >= 0 and current_gap < 0:
        return "死亡交叉"
    return "無"


def detect_cross_up(series_a: list[float], series_b: list[float]) -> bool:
    return len(series_a) >= 2 and len(series_b) >= 2 and series_a[-2] <= series_b[-2] and series_a[-1] > series_b[-1]


def detect_cross_down(series_a: list[float], series_b: list[float]) -> bool:
    return len(series_a) >= 2 and len(series_b) >= 2 and series_a[-2] >= series_b[-2] and series_a[-1] < series_b[-1]


def classify_direction(series: list[float], min_threshold: float = 0.0) -> str:
    if len(series) < 2:
        return "資料不足"

    delta = series[-1] - series[-2]
    threshold = max(min_threshold, _dynamic_threshold(series, ratio=0.005))

    if abs(delta) <= threshold:
        return "走平"
    return "上行" if delta > 0 else "下行"


def classify_curve(series: list[float], min_threshold: float = 0.0) -> str:
    if len(series) < 3:
        return "資料不足"

    slope_1 = series[-2] - series[-3]
    slope_2 = series[-1] - series[-2]
    delta = slope_2 - slope_1
    threshold = max(min_threshold, _dynamic_threshold(series, ratio=0.01))

    if abs(delta) <= threshold:
        return "走平"
    return "向上彎曲" if delta > 0 else "向下彎曲"


def classify_zero_axis(value: float, min_threshold: float = 0.01) -> str:
    if abs(value) <= min_threshold:
        return "貼近零軸"
    return "零上" if value > 0 else "零下"


def _ema(values: list[float], period: int) -> list[float]:
    multiplier = 2.0 / (period + 1.0)
    results: list[float] = []
    previous = values[0]

    for value in values:
        previous = ((value - previous) * multiplier) + previous
        results.append(previous)

    return results


def _dynamic_threshold(series: list[float], ratio: float) -> float:
    scale = max(1.0, max(abs(item) for item in series[-5:]))
    return scale * ratio
