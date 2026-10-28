from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from receitas.errors import DataImportError
from receitas.models import ForecastResult


LAG_WINDOW = 12
MIN_RANDOM_FOREST_TRAINING_SAMPLES = 24
RANDOM_FOREST_PARAMETERS = {
    "n_estimators": 200,
    "max_depth": 4,
    "min_samples_leaf": 2,
    "random_state": 42,
    "n_jobs": 1,
}


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


def _forecast_features(history: list[float], target: pd.Period) -> list[float]:
    month_angle = 2 * np.pi * (target.month - 1) / 12
    return [*reversed(history[-LAG_WINDOW:]), np.sin(month_angle), np.cos(month_angle)]


def random_forest_forecast(history: pd.Series, dates: pd.PeriodIndex) -> pd.Series:
    if len(history) <= LAG_WINDOW:
        raise _forecast_error(
            "o histórico é curto demais para construir defasagens mensais",
            "forneça mais observações antes de aplicar o modelo",
        )

    values = history.astype(float).tolist()
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(LAG_WINDOW, len(values)):
        target_period = history.index[index]
        features.append(_forecast_features(values[:index], target_period))
        targets.append(values[index])

    model = RandomForestRegressor(**RANDOM_FOREST_PARAMETERS)
    model.fit(np.asarray(features, dtype=float), np.asarray(targets, dtype=float))

    predictions: list[float] = []
    for target_period in dates:
        feature = np.asarray([_forecast_features(values, target_period)], dtype=float)
        prediction = float(model.predict(feature)[0])
        predictions.append(prediction)
        values.append(prediction)
    return pd.Series(predictions, index=dates, dtype=float)


def evaluate_and_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    validate_forecast_series(series)
    if horizon < 1:
        raise ValueError("Forecast horizon must be positive")
    numeric = series.astype(float)
    holdout = numeric.iloc[-12:]
    training = numeric.iloc[:-12]

    seasonal_holdout = seasonal_naive(training, holdout.index)
    trailing_holdout = trailing_mean(training, holdout.index, window=12)
    validation_predictions = {
        "Sazonal ingênuo": seasonal_holdout,
        "Média móvel de 12 meses": trailing_holdout,
    }
    if len(training) - LAG_WINDOW >= MIN_RANDOM_FOREST_TRAINING_SAMPLES:
        validation_predictions["Random Forest"] = random_forest_forecast(
            training, holdout.index
        )
    mae_by_method = {
        method: mean_absolute_error(holdout, predicted)
        for method, predicted in validation_predictions.items()
    }

    future_dates = pd.period_range(numeric.index.max() + 1, periods=horizon, freq="M")
    method = min(
        mae_by_method,
        key=lambda name: (
            mae_by_method[name],
            0 if name == "Sazonal ingênuo" else 1,
        ),
    )
    if method == "Sazonal ingênuo":
        estimated = seasonal_naive(numeric, future_dates)
    elif method == "Média móvel de 12 meses":
        estimated = trailing_mean(numeric, future_dates, window=12)
    else:
        estimated = random_forest_forecast(numeric, future_dates)

    return ForecastResult(
        method=method,
        mae=mae_by_method[method],
        mae_by_method=mae_by_method,
        holdout_start=holdout.index.min(),
        holdout_end=holdout.index.max(),
        horizon_start=future_dates.min(),
        horizon_end=future_dates.max(),
        observed=numeric.copy(),
        validation_estimated=validation_predictions[method],
        estimated=estimated,
    )
