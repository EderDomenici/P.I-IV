from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

import pandas as pd

from receitas.errors import DataImportError


CANONICAL_COLUMNS = [
    "period",
    "fiscal_year",
    "month",
    "revenue_code",
    "revenue_description",
    "category",
    "resource_source",
    "application_code",
    "initial_forecast",
    "updated_forecast",
    "collected_period",
    "collected_cumulative",
    "hierarchy_level",
    "is_aggregate",
    "source_file",
    "source_row",
    "source_kind",
]

TCE_REQUIRED_COLUMNS = {
    "id_rec_arrec_detalhe",
    "ano_exercicio",
    "mes_referencia",
    "ds_fonte_recurso",
    "ds_cd_aplicacao_fixo",
    "ds_cd_aplicacao_variavel",
    "vl_arrecadacao",
}


def parse_brazilian_decimal(value: object) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace("R$", "").replace("\xa0", "").replace(" ", "")
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise ValueError(f"Invalid Brazilian decimal: {value!r}") from error


def _split_code_description(value: object) -> tuple[str, str]:
    code, separator, description = str(value).partition(" - ")
    return code.strip(), description.strip() if separator else ""


def normalize_tce_file(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    missing = sorted(TCE_REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise DataImportError(
            path.name,
            f"colunas obrigatórias ausentes: {', '.join(missing)}",
            "gere novamente o recorte a partir do conjunto oficial do TCE-SP",
        )

    detail_column = "ds_tipo" if "ds_tipo" in frame.columns else "ds_subalinea"
    if detail_column not in frame.columns:
        raise DataImportError(
            path.name,
            "não foi encontrada uma coluna de detalhe da receita (ds_tipo ou ds_subalinea)",
            "verifique o esquema anual publicado pelo TCE-SP",
        )
    identities = frame[detail_column].map(_split_code_description)
    years = frame["ano_exercicio"].astype(int)
    months = frame["mes_referencia"].astype(int)
    normalized = pd.DataFrame(
        {
            "period": pd.PeriodIndex.from_fields(year=years, month=months, freq="M"),
            "fiscal_year": years,
            "month": months,
            "revenue_code": identities.map(lambda item: item[0]),
            "revenue_description": identities.map(lambda item: item[1]),
            "category": None,
            "resource_source": frame["ds_fonte_recurso"],
            "application_code": (
                frame["ds_cd_aplicacao_fixo"].str.strip()
                + " | "
                + frame["ds_cd_aplicacao_variavel"].str.strip()
            ),
            "initial_forecast": None,
            "updated_forecast": None,
            "collected_period": frame["vl_arrecadacao"].map(parse_brazilian_decimal),
            "collected_cumulative": None,
            "hierarchy_level": "detail",
            "is_aggregate": False,
            "source_file": path.name,
            "source_row": frame["id_rec_arrec_detalhe"],
            "source_kind": "tce",
        }
    )
    hierarchy_columns = [
        "ds_categoria",
        "ds_subcategoria",
        "ds_fonte",
        "ds_d1",
        "ds_dd2",
        "ds_d3",
        "ds_tipo",
        "ds_rubrica",
        "ds_alinea",
        "ds_subalinea",
    ]
    for column in hierarchy_columns:
        if column in frame.columns:
            normalized[f"source_hierarchy_{column.removeprefix('ds_')}"] = frame[column]
    return normalized


def _normalize_heading(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def _column(columns: set[str], aliases: tuple[str, ...], *, required: bool = False) -> str | None:
    matches = [alias for alias in aliases if alias in columns]
    if len(matches) == 1:
        return matches[0]
    if required:
        reason = "nenhuma coluna compatível" if not matches else "mais de uma coluna compatível"
        raise ValueError(f"{reason} para {aliases[0]}")
    return None


def _read_manual(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, sep=None, engine="python", dtype=str, keep_default_na=False)
    if suffix in {".xls", ".xlsx"}:
        return pd.read_excel(path, dtype=str, keep_default_na=False)
    raise DataImportError(
        path.name,
        f"formato {suffix or 'sem extensão'} não suportado",
        "use um arquivo CSV, XLS ou XLSX",
    )


def _clean_code(value: object) -> str:
    return re.sub(r"\.0$", "", str(value).strip())


def _parse_money_column(series: pd.Series, path: Path, label: str) -> pd.Series:
    try:
        return series.map(parse_brazilian_decimal)
    except ValueError as error:
        raise DataImportError(
            path.name,
            f"há valor monetário inválido na coluna {label}",
            "corrija o valor usando número ou formato brasileiro, por exemplo 1.234,56",
        ) from error


def _aggregate_flag(value: object) -> bool | pd._libs.missing.NAType:
    normalized = _normalize_heading(value)
    if normalized in {"detalhe", "detalhada", "analitica", "analitico"}:
        return False
    if normalized in {"agregado", "agregada", "sintetica", "sintetico", "total"}:
        return True
    return pd.NA


def normalize_manual_file(
    path: Path,
    value_semantics: Literal["period", "cumulative"] | None,
) -> pd.DataFrame:
    if value_semantics is None:
        raise DataImportError(
            path.name,
            "não foi informado se a coluna de valor representa o período ou o acumulado",
            "informe se os valores são do período ou acumulados",
        )
    frame = _read_manual(path)
    frame.columns = [_normalize_heading(column) for column in frame.columns]
    columns = set(frame.columns)
    try:
        year_column = _column(columns, ("ano", "ano_exercicio", "exercicio"), required=True)
        month_column = _column(columns, ("mes", "mes_referencia"), required=True)
        code_column = _column(columns, ("codigo", "codigo_receita", "receita_codigo"), required=True)
        description_column = _column(
            columns,
            ("especificacao", "descricao", "descricao_receita"),
            required=True,
        )
        if value_semantics == "period":
            value_column = _column(
                columns,
                ("arrecadado_periodo", "arrecadacao_periodo", "valor"),
                required=True,
            )
        else:
            value_column = _column(
                columns,
                ("arrecadado_acumulado", "arrecadacao_acumulada", "valor"),
                required=True,
            )
    except ValueError as error:
        raise DataImportError(
            path.name,
            str(error),
            "revise os nomes das colunas conforme o README",
        ) from error

    years = frame[year_column].astype(int)
    months = frame[month_column].astype(int)
    source_column = _column(columns, ("fonte", "fonte_recurso"))
    application_column = _column(columns, ("codigo_aplicacao", "aplicacao"))
    line_type_column = _column(columns, ("tipo_linha", "nivel", "nivel_hierarquico"))
    initial_column = _column(columns, ("previsao_inicial",))
    updated_column = _column(columns, ("previsao_atualizada",))
    values = _parse_money_column(frame[value_column], path, value_column)
    normalized = pd.DataFrame(
        {
            "period": pd.PeriodIndex.from_fields(year=years, month=months, freq="M"),
            "fiscal_year": years,
            "month": months,
            "revenue_code": frame[code_column].map(_clean_code),
            "revenue_description": frame[description_column].astype(str).str.strip(),
            "category": None,
            "resource_source": frame[source_column] if source_column else None,
            "application_code": frame[application_column] if application_column else None,
            "initial_forecast": (
                _parse_money_column(frame[initial_column], path, initial_column)
                if initial_column
                else None
            ),
            "updated_forecast": (
                _parse_money_column(frame[updated_column], path, updated_column)
                if updated_column
                else None
            ),
            "collected_period": values if value_semantics == "period" else None,
            "collected_cumulative": values if value_semantics == "cumulative" else None,
            "hierarchy_level": frame[line_type_column] if line_type_column else None,
            "is_aggregate": (
                frame[line_type_column].map(_aggregate_flag) if line_type_column else pd.NA
            ),
            "source_file": path.name,
            "source_row": [str(index + 2) for index in range(len(frame))],
            "source_kind": "manual",
        }
    )
    if value_semantics == "cumulative":
        normalized = to_period_values(normalized)
    return normalized


def to_period_values(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    identity_columns = [
        column
        for column in ("revenue_code", "resource_source", "application_code")
        if column in result.columns
    ]
    converted: dict[object, Decimal] = {}
    grouped = result.groupby(identity_columns, dropna=False, sort=False) if identity_columns else [((), result)]
    for _, group in grouped:
        ordered = group.sort_values("period")
        periods = pd.PeriodIndex(ordered["period"], freq="M")
        expected = pd.period_range(periods.min(), periods.max(), freq="M")
        if not periods.equals(expected):
            file_name = str(ordered["source_file"].iloc[0])
            raise DataImportError(
                file_name,
                "há uma lacuna mensal na série acumulada",
                "forneça todos os meses consecutivos antes de calcular valores do período",
            )
        previous: Decimal | None = None
        for index, cumulative in zip(ordered.index, ordered["collected_cumulative"], strict=True):
            if cumulative is None or pd.isna(cumulative):
                raise DataImportError(
                    str(ordered["source_file"].iloc[0]),
                    "há valor acumulado vazio",
                    "preencha ou remova a linha inválida na fonte",
                )
            current = Decimal(cumulative)
            converted[index] = current if previous is None else current - previous
            previous = current
    result["collected_period"] = pd.Series(converted)
    return result.sort_values(["period", "revenue_code"]).reset_index(drop=True)
