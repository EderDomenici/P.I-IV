from decimal import Decimal

import pandas as pd

from receitas.analysis import (
    equivalent_period_comparison,
    monthly_series,
    revenue_composition,
    summary_metrics,
)


def test_summary_metrics_does_not_invent_missing_budget() -> None:
    frame = pd.DataFrame(
        {
            "collected_period": [Decimal("100"), Decimal("50")],
            "updated_forecast": [None, None],
        }
    )

    metrics = summary_metrics(frame)

    assert metrics.collected == Decimal("150")
    assert metrics.updated_forecast is None
    assert metrics.realized_percentage is None


def test_summary_metrics_calculates_realized_percentage() -> None:
    frame = pd.DataFrame(
        {
            "collected_period": [Decimal("75"), Decimal("25")],
            "updated_forecast": [Decimal("200"), None],
        }
    )

    metrics = summary_metrics(frame)

    assert metrics.updated_forecast == Decimal("200")
    assert metrics.realized_percentage == Decimal("50.0")


def test_summary_metrics_does_not_repeat_annual_budget_across_months() -> None:
    frame = pd.DataFrame(
        {
            "period": [pd.Period("2026-01", freq="M"), pd.Period("2026-02", freq="M")],
            "revenue_code": ["11125001", "11125001"],
            "resource_source": ["Tesouro", "Tesouro"],
            "application_code": ["Geral", "Geral"],
            "collected_period": [Decimal("75"), Decimal("25")],
            "updated_forecast": [Decimal("200"), Decimal("200")],
        }
    )

    metrics = summary_metrics(frame)

    assert metrics.updated_forecast == Decimal("200")
    assert metrics.realized_percentage == Decimal("50.0")


def test_monthly_series_preserves_negative_adjustments() -> None:
    frame = pd.DataFrame(
        {
            "period": [pd.Period("2025-01", freq="M")] * 2,
            "fiscal_year": [2025, 2025],
            "month": [1, 1],
            "category": ["IPTU", "IPTU"],
            "collected_period": [Decimal("100"), Decimal("-10")],
        }
    )

    result = monthly_series(frame)

    assert result.loc[0, "amount"] == Decimal("90")


def test_equivalent_period_comparison_truncates_all_years_to_partial_window() -> None:
    rows: list[dict[str, object]] = []
    for year, last_month in {2024: 12, 2025: 12, 2026: 8}.items():
        for month in range(1, last_month + 1):
            rows.append(
                {
                    "period": pd.Period(year=year, month=month, freq="M"),
                    "fiscal_year": year,
                    "month": month,
                    "category": "FPM",
                    "collected_period": Decimal("100"),
                }
            )
    frame = pd.DataFrame(rows)

    result = equivalent_period_comparison(frame, [2024, 2025, 2026])

    assert result["comparison_last_month"].unique().tolist() == [8]
    assert result.groupby("fiscal_year")["month"].max().to_dict() == {
        2024: 8,
        2025: 8,
        2026: 8,
    }


def test_composition_groups_only_remainder_as_other() -> None:
    frame = pd.DataFrame(
        {
            "category": ["FPM", "ICMS", "Small A", "Small B"],
            "collected_period": [
                Decimal("500"),
                Decimal("400"),
                Decimal("30"),
                Decimal("20"),
            ],
        }
    )

    result = revenue_composition(frame, top_n=2)

    assert result["category"].tolist() == ["FPM", "ICMS", "Outras receitas"]
    assert result["amount"].sum() == Decimal("950")
