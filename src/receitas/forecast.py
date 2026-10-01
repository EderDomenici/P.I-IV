from __future__ import annotations

import numpy as np
import pandas as pd

from receitas.errors import DataImportError
from receitas.models import ForecastResult


def _forecast_error(reason: str, action: str) -> DataImportError:
    return DataImportError("série selecionada", reason, action)


def validate_forecast_series(series: pd.Series, minimum_months: int = 36) -> None:
    if not isinstance(series.index, pd.PeriodIndex) or series.index.freqstr != "M":
        raise _forecast_error(
            "o índice não representa competências mensais",
            "prepare uma série mensal antes da previsão",
        )
    if not series.index.is_monotonic_increasing or not series.index.is_unique:
        raise _forecast_error(
            "as competências estão fora de ordem ou repetidas",
            "ordene e agregue a série por mês",
        )
    if len(series) < minimum_months:
        raise _forecast_error(
            f"a previsão exige pelo menos {minimum_months} meses completos",
            "forneça mais histórico mensal",
        )
    expected = pd.period_range(series.index.min(), series.index.max(), freq="M")
    if not series.index.equals(expected):
        raise _forecast_error(
            "há pelo menos um mês ausente na série",
            "complete a sequência mensal sem interpolar valores silenciosamente",
        )
    if series.isna().any():
        raise _forecast_error(
            "há valores vazios na série",
            "corrija os meses sem valor na fonte",
        )


def seasonal_naive(history: pd.Series, dates: pd.PeriodIndex) -> pd.Series:
    known = {period: float(value) for period, value in history.items()}
    predictions: list[float] = []
    for date in dates:
        reference = date - 12
        if reference not in known:
            raise _forecast_error(
                f"não existe observação para {reference}",
                "use uma série com pelo menos um ciclo sazonal anterior",
            )
        prediction = known[reference]
        predictions.append(prediction)
        known[date] = prediction
    return pd.Series(predictions, index=dates, dtype=float)


def trailing_mean(
    history: pd.Series,
    dates: pd.PeriodIndex,
    window: int = 12,
) -> pd.Series:
    values = [float(value) for value in history]
    predictions: list[float] = []
    for _ in dates:
        available = values[-window:]
        if not available:
            raise _forecast_error("a série está vazia", "forneça histórico mensal")
        prediction = float(np.mean(available))
        predictions.append(prediction)
        values.append(prediction)
    return pd.Series(predictions, index=dates, dtype=float)


def mean_absolute_error(observed: pd.Series, predicted: pd.Series) -> float:
    if not observed.index.equals(predicted.index):
        raise ValueError("Observed and predicted indexes must match")
    return float(np.mean(np.abs(observed.astype(float) - predicted.astype(float))))


def evaluate_and_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    validate_forecast_series(series)
    if horizon < 1:
        raise ValueError("Forecast horizon must be positive")
    numeric = series.astype(float)
    holdout = numeric.iloc[-12:]
    training = numeric.iloc[:-12]

    seasonal_holdout = seasonal_naive(training, holdout.index)
    trailing_holdout = trailing_mean(training, holdout.index, window=12)
    seasonal_mae = mean_absolute_error(holdout, seasonal_holdout)
    trailing_mae = mean_absolute_error(holdout, trailing_holdout)

    future_dates = pd.period_range(numeric.index.max() + 1, periods=horizon, freq="M")
    if seasonal_mae <= trailing_mae:
        method = "Sazonal ingênuo"
        mae = seasonal_mae
        estimated = seasonal_naive(numeric, future_dates)
    else:
        method = "Média móvel de 12 meses"
        mae = trailing_mae
        estimated = trailing_mean(numeric, future_dates, window=12)

    return ForecastResult(
        method=method,
        mae=mae,
        holdout_start=holdout.index.min(),
        holdout_end=holdout.index.max(),
        horizon_start=future_dates.min(),
        horizon_end=future_dates.max(),
        observed=numeric.copy(),
        estimated=estimated,
    )
