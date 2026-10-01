from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from app import (
    format_brl_currency,
    format_percentage,
    forecast_for_selection,
    load_dashboard_data,
    month_name_pt,
    run_app_safely,
    select_forecast_candidate,
    validation_issue_message_pt,
)
from receitas.errors import DataImportError


def test_currency_format_uses_brazilian_separators() -> None:
    assert format_brl_currency(Decimal("1234567.89")) == "R$ 1.234.567,89"
    assert format_brl_currency(Decimal("-10.5")) == "-R$ 10,50"


def test_percentage_format_uses_brazilian_decimal() -> None:
    assert format_percentage(Decimal("72.345")) == "72,35%"
    assert format_percentage(None) == "Não disponível"


def test_load_dashboard_data_reports_missing_preparation(tmp_path: Path) -> None:
    with pytest.raises(DataImportError, match="Parquet preparado não foi encontrado"):
        load_dashboard_data(tmp_path / "missing.parquet")


def test_select_forecast_candidate_prefers_complete_series() -> None:
    rows: list[dict[str, object]] = []
    for period in pd.period_range("2021-01", periods=60, freq="M"):
        rows.append({"period": period, "category": "FPM", "collected_period": Decimal("100")})
    for period in pd.period_range("2023-01", periods=24, freq="M"):
        rows.append({"period": period, "category": "ICMS", "collected_period": Decimal("200")})

    candidate = select_forecast_candidate(pd.DataFrame(rows))

    assert candidate.category == "FPM"
    assert len(candidate.series) == 60


def test_select_forecast_candidate_explains_insufficient_data() -> None:
    frame = pd.DataFrame(
        {
            "period": pd.period_range("2025-01", periods=12, freq="M"),
            "category": ["FPM"] * 12,
            "collected_period": [Decimal("100")] * 12,
        }
    )

    with pytest.raises(DataImportError, match="nenhuma categoria"):
        select_forecast_candidate(frame)


def test_validation_issue_message_translates_known_codes_and_preserves_fallback() -> None:
    assert validation_issue_message_pt("BUDGET_UNAVAILABLE", "English") == (
        "A fonte do TCE-SP não fornece previsão orçamentária atualizada."
    )
    assert validation_issue_message_pt("UNKNOWN", "Mensagem original") == "Mensagem original"


def test_forecast_for_selection_uses_filtered_category_and_remaining_year_horizon() -> None:
    rows: list[dict[str, object]] = []
    for period in pd.period_range("2023-01", periods=44, freq="M"):
        rows.append(
            {"period": period, "category": "ICMS", "collected_period": Decimal("200")}
        )

    candidate, result = forecast_for_selection(pd.DataFrame(rows))

    assert candidate.category == "ICMS"
    assert result.horizon_start == pd.Period("2026-09", freq="M")
    assert result.horizon_end == pd.Period("2026-12", freq="M")


def test_month_name_is_presented_in_portuguese() -> None:
    assert month_name_pt(8) == "agosto"


def test_run_app_safely_hides_unexpected_technical_error(caplog: pytest.LogCaptureFixture) -> None:
    messages: list[str] = []

    def broken_render() -> None:
        raise RuntimeError("internal database detail")

    run_app_safely(broken_render, messages.append)

    assert messages == ["Ocorreu um erro inesperado ao carregar o painel."]
    assert "internal database detail" in caplog.text
