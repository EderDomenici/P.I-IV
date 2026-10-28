import pandas as pd
import pytest

import receitas.forecast as forecast_module
from receitas.errors import DataImportError
from receitas.forecast import (
    evaluate_and_forecast,
    mean_absolute_error,
    random_forest_forecast,
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


def test_random_forest_forecast_is_recursive_and_aligned_to_requested_months() -> None:
    history = monthly_values("2021-01", 36)
    dates = pd.period_range("2024-01", periods=3, freq="M")

    result = random_forest_forecast(history, dates)

    assert result.index.equals(dates)
    assert result.notna().all()
    assert result.dtype == float


def test_evaluation_selects_lower_mae_and_keeps_estimates_separate() -> None:
    index = pd.period_range("2021-01", periods=60, freq="M")
    series = pd.Series([float(period.month * 100) for period in index], index=index)

    result = evaluate_and_forecast(series, horizon=6)

    assert result.method == "Sazonal ingênuo"
    assert result.mae == 0.0
    assert result.observed.index.max() < result.estimated.index.min()
    assert result.holdout_start == pd.Period("2025-01", freq="M")
    assert result.holdout_end == pd.Period("2025-12", freq="M")
    assert result.validation_estimated.index.equals(
        pd.period_range("2025-01", periods=12, freq="M")
    )
    assert result.mae == min(result.mae_by_method.values())
    assert len(result.estimated) == 6


def test_random_forest_is_excluded_when_training_sample_count_is_too_small() -> None:
    series = monthly_values("2021-01", 36)

    result = evaluate_and_forecast(series, horizon=3)

    assert "Random Forest" not in result.mae_by_method
    assert result.method in {"Sazonal ingênuo", "Média móvel de 12 meses"}


def test_random_forest_holdout_training_does_not_include_holdout_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    series = pd.Series(
        [float(value) for value in range(1, 61)],
        index=pd.period_range("2021-01", periods=60, freq="M"),
    )
    trained_targets: list[list[float]] = []

    class RecordingRegressor:
        def __init__(self, **_: object) -> None:
            pass

        def fit(self, features: object, targets: object) -> object:
            trained_targets.append(list(targets))
            return self

        def predict(self, features: object) -> list[float]:
            return [0.0]

    monkeypatch.setattr(forecast_module, "RandomForestRegressor", RecordingRegressor)

    evaluate_and_forecast(series, horizon=3)

    assert trained_targets[0] == series.iloc[12:-12].tolist()
