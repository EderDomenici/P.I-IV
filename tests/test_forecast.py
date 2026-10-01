import pandas as pd
import pytest

from receitas.errors import DataImportError
from receitas.forecast import (
    evaluate_and_forecast,
    mean_absolute_error,
    seasonal_naive,
    trailing_mean,
    validate_forecast_series,
)


def monthly_values(start: str, periods: int) -> pd.Series:
    index = pd.period_range(start, periods=periods, freq="M")
    return pd.Series([float((period.month * 10) + period.year - 2020) for period in index], index=index)


def test_forecast_rejects_fewer_than_36_months() -> None:
    with pytest.raises(DataImportError, match="36 meses completos"):
        validate_forecast_series(monthly_values("2021-01", 35))


def test_forecast_rejects_missing_month_without_interpolation() -> None:
    series = monthly_values("2021-01", 48).drop(pd.Period("2023-07", freq="M"))

    with pytest.raises(DataImportError, match="mês ausente"):
        validate_forecast_series(series)


def test_seasonal_naive_uses_same_month_of_previous_year() -> None:
    history = monthly_values("2021-01", 36)
    dates = pd.period_range("2024-01", periods=3, freq="M")

    result = seasonal_naive(history, dates)

    assert result.tolist() == history.loc["2023-01":"2023-03"].tolist()


def test_trailing_mean_is_recursive() -> None:
    history = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.period_range("2025-01", periods=3, freq="M"),
    )
    dates = pd.period_range("2025-04", periods=2, freq="M")

    result = trailing_mean(history, dates, window=2)

    assert result.tolist() == [2.5, 2.75]


def test_mean_absolute_error_uses_aligned_holdout_observations() -> None:
    index = pd.period_range("2025-01", periods=2, freq="M")
    observed = pd.Series([100.0, 120.0], index=index)
    predicted = pd.Series([90.0, 140.0], index=index)

    assert mean_absolute_error(observed, predicted) == 15.0


def test_evaluation_selects_lower_mae_and_keeps_estimates_separate() -> None:
    index = pd.period_range("2021-01", periods=60, freq="M")
    series = pd.Series([float(period.month * 100) for period in index], index=index)

    result = evaluate_and_forecast(series, horizon=6)

    assert result.method == "Sazonal ingênuo"
    assert result.mae == 0.0
    assert result.observed.index.max() < result.estimated.index.min()
    assert result.holdout_start == pd.Period("2025-01", freq="M")
    assert len(result.estimated) == 6
