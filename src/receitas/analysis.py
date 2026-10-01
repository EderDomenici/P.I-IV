from __future__ import annotations

from decimal import Decimal
from typing import Sequence

import pandas as pd

from receitas.models import SummaryMetrics


ZERO = Decimal("0")


def _decimal_sum(values: pd.Series) -> Decimal:
    return sum((Decimal(value) for value in values.dropna()), ZERO)


def summary_metrics(frame: pd.DataFrame) -> SummaryMetrics:
    collected = _decimal_sum(frame["collected_period"])
    forecasts = frame["updated_forecast"].dropna()
    updated_forecast: Decimal | None = None
    if not forecasts.empty:
        identity_columns = [
            column
            for column in (
                "fiscal_year",
                "revenue_code",
                "resource_source",
                "application_code",
            )
            if column in frame.columns
        ]
        if identity_columns and "period" in frame.columns:
            latest = (
                frame.loc[frame["updated_forecast"].notna()]
                .sort_values("period")
                .groupby(identity_columns, dropna=False, sort=False)
                .tail(1)
            )
            updated_forecast = _decimal_sum(latest["updated_forecast"])
        else:
            updated_forecast = _decimal_sum(forecasts)
    realized_percentage: Decimal | None = None
    if updated_forecast not in {None, ZERO}:
        realized_percentage = collected / updated_forecast * Decimal("100")
    return SummaryMetrics(collected, updated_forecast, realized_percentage)


def monthly_series(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["period", "fiscal_year", "month", "category", "amount"])
    rows: list[dict[str, object]] = []
    group_columns = ["period", "fiscal_year", "month", "category"]
    for keys, group in frame.groupby(group_columns, dropna=False, sort=True):
        period, year, month, category = keys
        rows.append(
            {
                "period": period,
                "fiscal_year": int(year),
                "month": int(month),
                "category": category,
                "amount": _decimal_sum(group["collected_period"]),
            }
        )
    return pd.DataFrame(rows)


def revenue_composition(frame: pd.DataFrame, top_n: int = 9) -> pd.DataFrame:
    totals = [
        {"category": category, "amount": _decimal_sum(group["collected_period"])}
        for category, group in frame.groupby("category", dropna=False, sort=False)
    ]
    totals.sort(key=lambda item: item["amount"], reverse=True)
    principal = totals[:top_n]
    remainder = sum((item["amount"] for item in totals[top_n:]), ZERO)
    if totals[top_n:]:
        principal.append({"category": "Outras receitas", "amount": remainder})
    return pd.DataFrame(principal, columns=["category", "amount"])


def equivalent_period_comparison(
    frame: pd.DataFrame,
    years: Sequence[int],
) -> pd.DataFrame:
    selected = frame.loc[frame["fiscal_year"].isin(years)].copy()
    available_years = set(int(year) for year in selected["fiscal_year"].unique())
    missing = set(years).difference(available_years)
    if missing:
        raise ValueError(f"Years without data: {sorted(missing)}")
    last_month = min(
        int(group["month"].max()) for _, group in selected.groupby("fiscal_year", sort=True)
    )
    selected = selected.loc[selected["month"] <= last_month]
    rows: list[dict[str, object]] = []
    for (year, month), group in selected.groupby(["fiscal_year", "month"], sort=True):
        rows.append(
            {
                "fiscal_year": int(year),
                "month": int(month),
                "amount": _decimal_sum(group["collected_period"]),
                "comparison_last_month": last_month,
            }
        )
    return pd.DataFrame(rows)
