from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from receitas.errors import DataImportError
from receitas.importers import (
    normalize_manual_file,
    normalize_tce_file,
    parse_brazilian_decimal,
    to_period_values,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", Decimal("1234.56")),
        ("-98,10", Decimal("-98.10")),
        ("R$ 0,00", Decimal("0.00")),
        (123.45, Decimal("123.45")),
        ("", None),
        (None, None),
    ],
)
def test_parse_brazilian_decimal(raw: object, expected: Decimal | None) -> None:
    assert parse_brazilian_decimal(raw) == expected


def _write_tce_fixture(tmp_path: Path) -> Path:
    frame = pd.DataFrame(
        {
            "id_rec_arrec_detalhe": ["0001", "0002"],
            "ano_exercicio": ["2025", "2025"],
            "ds_municipio": ["Martinópolis", "Martinópolis"],
            "ds_orgao": ["PREFEITURA", "PREFEITURA"],
            "mes_referencia": ["1", "2"],
            "mes_ref_extenso": ["Janeiro", "Fevereiro"],
            "ds_poder": ["EXECUTIVO", "EXECUTIVO"],
            "ds_fonte_recurso": ["01 - TESOURO", "01 - TESOURO"],
            "ds_cd_aplicacao_fixo": ["110 - GERAL", "110 - GERAL"],
            "ds_cd_aplicacao_variavel": ["00 - NÃO INFORMADO", "00 - NÃO INFORMADO"],
            "ds_categoria": ["10000000 - Receitas Correntes"] * 2,
            "ds_subcategoria": ["11000000 - Impostos"] * 2,
            "ds_fonte": ["11100000 - Impostos"] * 2,
            "ds_d1": ["11120000 - Patrimônio"] * 2,
            "ds_dd2": ["11125000 - IPTU"] * 2,
            "ds_d3": ["11125000 - IPTU"] * 2,
            "ds_tipo": ["011125001 - IPTU - Principal", "011125001 - IPTU - Principal"],
            "vl_arrecadacao": ["767,79", "-10,00"],
        }
    )
    path = tmp_path / "martinopolis-receitas-2025.csv"
    frame.to_csv(path, sep=";", index=False, encoding="utf-8")
    return path


def test_normalize_tce_file_builds_monthly_detail_rows(tmp_path: Path) -> None:
    path = _write_tce_fixture(tmp_path)

    result = normalize_tce_file(path)

    assert result.loc[0, "period"] == pd.Period("2025-01", freq="M")
    assert result.loc[0, "revenue_code"] == "011125001"
    assert result.loc[0, "revenue_description"] == "IPTU - Principal"
    assert result.loc[0, "collected_period"] == Decimal("767.79")
    assert result.loc[1, "collected_period"] == Decimal("-10.00")
    assert result.loc[0, "is_aggregate"] == False  # noqa: E712
    assert result.loc[0, "source_row"] == "0001"


def test_normalize_legacy_2021_tce_schema_uses_subalinea_as_detail(tmp_path: Path) -> None:
    path = tmp_path / "martinopolis-receitas-2021.csv"
    pd.DataFrame(
        {
            "id_rec_arrec_detalhe": ["32557129"],
            "ano_exercicio": ["2021"],
            "ds_municipio": ["Martinópolis"],
            "ds_orgao": ["PREFEITURA"],
            "mes_referencia": ["1"],
            "mes_ref_extenso": ["Janeiro"],
            "ds_poder": ["EXECUTIVO"],
            "ds_fonte_recurso": ["01 - TESOURO"],
            "ds_cd_aplicacao_fixo": ["110 - GERAL"],
            "ds_cd_aplicacao_variavel": ["00 - NÃO INFORMADO"],
            "ds_categoria": ["10000000 - Receitas Correntes"],
            "ds_subcategoria": ["11000000 - Impostos"],
            "ds_fonte": ["11100000 - Impostos"],
            "ds_rubrica": ["11180000 - Impostos Específicos"],
            "ds_alinea": ["11180100 - Impostos sobre o Patrimônio"],
            "ds_subalinea": ["11180111 - IPTU - Principal"],
            "vl_arrecadacao": ["3550,08"],
        }
    ).to_csv(path, sep=";", index=False)

    result = normalize_tce_file(path)

    assert result.loc[0, "revenue_code"] == "11180111"
    assert result.loc[0, "revenue_description"] == "IPTU - Principal"
    assert result.loc[0, "source_hierarchy_subalinea"] == "11180111 - IPTU - Principal"


def test_manual_import_rejects_ambiguous_value_semantics(tmp_path: Path) -> None:
    path = tmp_path / "receitas-2026.csv"
    path.write_text(
        "ano;mes;codigo;especificacao;valor\n2026;1;11125001;IPTU;100,00\n",
        encoding="utf-8",
    )

    with pytest.raises(DataImportError) as captured:
        normalize_manual_file(path, value_semantics=None)

    assert path.name in captured.value.user_message
    assert "informe se os valores são do período ou acumulados" in captured.value.user_message


def test_manual_import_reports_invalid_currency_as_actionable_error(tmp_path: Path) -> None:
    path = tmp_path / "receitas-2026.csv"
    path.write_text(
        "ano;mes;codigo;especificacao;valor\n2026;1;11125001;IPTU;valor-invalido\n",
        encoding="utf-8",
    )

    with pytest.raises(DataImportError) as captured:
        normalize_manual_file(path, value_semantics="period")

    assert path.name in captured.value.user_message
    assert "valor monetário" in captured.value.user_message


def test_cumulative_conversion_rejects_missing_month() -> None:
    frame = pd.DataFrame(
        {
            "period": [pd.Period("2026-01", freq="M"), pd.Period("2026-03", freq="M")],
            "fiscal_year": [2026, 2026],
            "month": [1, 3],
            "revenue_code": ["11125001", "11125001"],
            "resource_source": ["Tesouro", "Tesouro"],
            "application_code": ["Geral", "Geral"],
            "collected_cumulative": [Decimal("100"), Decimal("160")],
            "source_file": ["2026.csv", "2026.csv"],
        }
    )

    with pytest.raises(DataImportError, match="lacuna mensal"):
        to_period_values(frame)


def test_cumulative_conversion_preserves_negative_adjustment() -> None:
    frame = pd.DataFrame(
        {
            "period": pd.period_range("2026-01", periods=3, freq="M"),
            "fiscal_year": [2026] * 3,
            "month": [1, 2, 3],
            "revenue_code": ["11125001"] * 3,
            "resource_source": ["Tesouro"] * 3,
            "application_code": ["Geral"] * 3,
            "collected_cumulative": [Decimal("100"), Decimal("150"), Decimal("140")],
            "source_file": ["2026.csv"] * 3,
        }
    )

    result = to_period_values(frame)

    assert result["collected_period"].tolist() == [
        Decimal("100"),
        Decimal("50"),
        Decimal("-10"),
    ]


def test_manual_xlsx_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "receitas-2026.xlsx"
    pd.DataFrame(
        {
            "ano": [2026],
            "mes": [1],
            "codigo": ["11125001"],
            "especificacao": ["IPTU - Principal"],
            "arrecadado_periodo": [100.5],
            "tipo_linha": ["detalhe"],
        }
    ).to_excel(path, index=False)

    result = normalize_manual_file(path, value_semantics="period")

    assert result.loc[0, "collected_period"] == Decimal("100.5")
    assert result.loc[0, "source_kind"] == "manual"
