from __future__ import annotations

import json
import logging
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from collections.abc import Callable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from receitas.analysis import (
    equivalent_period_comparison,
    monthly_series,
    revenue_composition,
    summary_metrics,
)
from receitas.config import PROCESSED_DIR
from receitas.errors import DataImportError
from receitas.forecast import evaluate_and_forecast, validate_forecast_series
from receitas.models import ForecastCandidate, ForecastResult


ISSUE_MESSAGES_PT: dict[str, str] = {
    "MISSING_COLUMNS": "O conjunto tratado não contém todas as colunas obrigatórias.",
    "DUPLICATE_SOURCE_ROW": "Existem linhas de origem duplicadas.",
    "INVALID_MONTH": "Existem competências com mês fora do intervalo de 1 a 12.",
    "MISSING_TRACEABILITY": "Existem registros sem identificação do arquivo e da linha de origem.",
    "AMBIGUOUS_HIERARCHY": "A hierarquia contábil contém linhas que ainda precisam ser classificadas.",
    "PARTIAL_YEAR": "O exercício contém somente parte dos meses do ano.",
    "BUDGET_UNAVAILABLE": "A fonte do TCE-SP não fornece previsão orçamentária atualizada.",
    "UNCLASSIFIED_REVENUE": "Alguns códigos permanecem em “Não classificada” e preservam o detalhamento original.",
}

MONTH_NAMES_PT: tuple[str, ...] = (
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def validation_issue_message_pt(code: str, fallback: str) -> str:
    return ISSUE_MESSAGES_PT.get(code, fallback)


def month_name_pt(month: int) -> str:
    if month not in range(1, 13):
        raise ValueError(f"Invalid month: {month}")
    return MONTH_NAMES_PT[month]


def format_brl_currency(value: Decimal) -> str:
    absolute = abs(value)
    formatted = f"{absolute:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    prefix = "-" if value < 0 else ""
    return f"{prefix}R$ {formatted}"


def format_percentage(value: Decimal | None) -> str:
    if value is None:
        return "Não disponível"
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{rounded:.2f}%".replace(".", ",")


def load_dashboard_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise DataImportError(
            path.name,
            "o Parquet preparado não foi encontrado",
            "execute os scripts download_tce_data.py e prepare_data.py",
        )
    frame = pd.read_parquet(path)
    required = {
        "period",
        "fiscal_year",
        "month",
        "category",
        "collected_period",
        "source_file",
        "source_row",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise DataImportError(
            path.name,
            f"faltam colunas processadas: {', '.join(missing)}",
            "execute novamente o preparo de dados",
        )
    frame["period"] = frame["period"].map(lambda value: pd.Period(str(value), freq="M"))
    return frame


def select_forecast_candidate(frame: pd.DataFrame) -> ForecastCandidate:
    candidates: list[ForecastCandidate] = []
    for category, group in frame.groupby("category", dropna=False, sort=True):
        if pd.isna(category) or category == "Não classificada":
            continue
        monthly = group.groupby("period")["collected_period"].apply(
            lambda values: float(sum(Decimal(value) for value in values))
        )
        monthly.index = pd.PeriodIndex(monthly.index, freq="M")
        monthly = monthly.sort_index()
        try:
            validate_forecast_series(monthly)
        except DataImportError:
            continue
        candidates.append(ForecastCandidate(str(category), monthly))
    if not candidates:
        raise DataImportError(
            "dados processados",
            "nenhuma categoria possui 36 meses completos e consecutivos",
            "adicione mais histórico ou revise lacunas e mudanças de classificação",
        )
    candidates.sort(
        key=lambda candidate: (
            -len(candidate.series),
            -abs(float(candidate.series.sum())),
            candidate.category,
        )
    )
    return candidates[0]


def forecast_for_selection(frame: pd.DataFrame) -> tuple[ForecastCandidate, ForecastResult]:
    candidate = select_forecast_candidate(frame)
    last_month = candidate.series.index.max().month
    horizon = 12 if last_month == 12 else 12 - last_month
    return candidate, evaluate_and_forecast(candidate.series, horizon=horizon)


def _chart_frame(frame: pd.DataFrame, amount_column: str = "amount") -> pd.DataFrame:
    result = frame.copy()
    result[amount_column] = result[amount_column].map(float)
    if "period" in result.columns:
        result["competência"] = result["period"].map(lambda value: value.to_timestamp())
    return result


def _load_validation_report(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"blocked": False, "issues": []}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    st.set_page_config(page_title="Receitas de Martinópolis", page_icon="📊", layout="wide")
    st.title("Receitas municipais de Martinópolis")
    st.caption(
        "Análise acadêmica com dados públicos. A ferramenta apoia a leitura humana e não identifica irregularidades."
    )

    try:
        frame = load_dashboard_data(PROCESSED_DIR / "revenues.parquet")
    except DataImportError as error:
        st.error(error.user_message)
        st.stop()

    available_years = sorted(int(year) for year in frame["fiscal_year"].unique())
    available_categories = sorted(str(value) for value in frame["category"].dropna().unique())
    st.sidebar.header("Filtros")
    years = st.sidebar.multiselect("Exercícios", available_years, default=available_years)
    categories = st.sidebar.multiselect(
        "Categorias",
        available_categories,
        default=available_categories,
    )
    filtered = frame.loc[
        frame["fiscal_year"].isin(years) & frame["category"].isin(categories)
    ].copy()

    if "resource_source" in filtered and filtered["resource_source"].notna().all():
        sources = sorted(str(value) for value in filtered["resource_source"].unique())
        if len(sources) > 1:
            chosen_sources = st.sidebar.multiselect("Fontes", sources, default=sources)
            filtered = filtered.loc[filtered["resource_source"].isin(chosen_sources)]
    if "application_code" in filtered and filtered["application_code"].notna().all():
        applications = sorted(str(value) for value in filtered["application_code"].unique())
        if 1 < len(applications) <= 30:
            chosen_applications = st.sidebar.multiselect(
                "Aplicações", applications, default=applications
            )
            filtered = filtered.loc[filtered["application_code"].isin(chosen_applications)]

    if filtered.empty:
        st.warning("Nenhum registro corresponde aos filtros selecionados.")
        st.stop()

    first_period = filtered["period"].min()
    last_period = filtered["period"].max()
    partial_label = ""
    if last_period.month < 12:
        partial_label = f" — {last_period.year} parcial até {month_name_pt(last_period.month)}"
    st.info(f"Período coberto: {first_period} a {last_period}{partial_label}")

    overview_tab, evolution_tab, comparison_tab, forecast_tab = st.tabs(
        ["Visão geral", "Evolução mensal", "Comparação entre anos", "Previsão e qualidade"]
    )

    with overview_tab:
        metrics = summary_metrics(filtered)
        collected_col, budget_col, realized_col = st.columns(3)
        collected_col.metric("Receita arrecadada", format_brl_currency(metrics.collected))
        budget_col.metric(
            "Previsão orçamentária",
            format_brl_currency(metrics.updated_forecast)
            if metrics.updated_forecast is not None
            else "Não disponível nesta fonte",
        )
        realized_col.metric("Percentual realizado", format_percentage(metrics.realized_percentage))
        composition = _chart_frame(revenue_composition(filtered))
        figure = px.pie(
            composition,
            names="category",
            values="amount",
            title="Composição da receita selecionada",
            hole=0.45,
        )
        st.plotly_chart(figure, width="stretch")

    with evolution_tab:
        evolution = _chart_frame(monthly_series(filtered))
        figure = px.line(
            evolution,
            x="competência",
            y="amount",
            color="category",
            labels={"amount": "Arrecadação (R$)", "category": "Categoria"},
            title="Evolução mensal",
            markers=True,
        )
        st.plotly_chart(figure, width="stretch")

    with comparison_tab:
        if len(years) < 2:
            st.info("Selecione pelo menos dois exercícios para comparar.")
        else:
            comparison = equivalent_period_comparison(filtered, years)
            last_comparable_month = int(comparison["comparison_last_month"].iloc[0])
            totals = comparison.groupby("fiscal_year", as_index=False)["amount"].apply(
                lambda values: float(sum(values))
            )
            figure = px.bar(
                totals,
                x="fiscal_year",
                y="amount",
                labels={"fiscal_year": "Exercício", "amount": "Arrecadação (R$)"},
                title=f"Comparação equivalente: janeiro ao mês {last_comparable_month}",
            )
            st.plotly_chart(figure, width="stretch")

    with forecast_tab:
        report = _load_validation_report(PROCESSED_DIR / "validation-report.json")
        try:
            candidate, forecast = forecast_for_selection(filtered)
        except DataImportError as error:
            st.info(error.user_message)
        else:
            figure = go.Figure()
            figure.add_trace(
                go.Scatter(
                    x=forecast.observed.index.to_timestamp(),
                    y=forecast.observed.values,
                    name="Observado",
                    mode="lines",
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=forecast.validation_estimated.index.to_timestamp(),
                    y=forecast.validation_estimated.values,
                    name="Estimado no teste histórico",
                    mode="lines+markers",
                    line={"dash": "dot"},
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=forecast.estimated.index.to_timestamp(),
                    y=forecast.estimated.values,
                    name="Projeção",
                    mode="lines+markers",
                    line={"dash": "dash"},
                )
            )
            figure.update_layout(title=f"Previsão para {candidate.category}", yaxis_title="R$")
            st.plotly_chart(figure, width="stretch")
            st.subheader("MAE no teste histórico")
            st.table(
                pd.DataFrame(
                    [
                        {
                            "Método": method,
                            "MAE (R$ por mês)": format_brl_currency(Decimal(str(mae))),
                        }
                        for method, mae in forecast.mae_by_method.items()
                    ]
                )
            )
            st.write(
                f"Categoria: **{candidate.category}** · Método: **{forecast.method}** · "
                f"MAE histórico: **{format_brl_currency(Decimal(str(forecast.mae)))}** · "
                f"Teste: **{forecast.holdout_start} a {forecast.holdout_end}** · "
                f"Horizonte: **{forecast.horizon_start} a {forecast.horizon_end}**"
            )
            st.caption(
                "A Random Forest usa até 12 defasagens mensais e seno/cosseno do mês. "
                "O MAE usa os 12 meses finais também empregados para selecionar o método; "
                "não há um teste posterior independente. Projeções são estimativas, não garantias."
            )

        st.subheader("Qualidade dos dados")
        issues = report.get("issues", [])
        if issues:
            for issue in issues:
                if isinstance(issue, dict):
                    code = str(issue.get("code", "UNKNOWN"))
                    message = validation_issue_message_pt(code, str(issue.get("message", "")))
                    st.write(f"- `{code}` — {message}")
        else:
            st.write("Nenhuma ocorrência registrada no relatório de validação.")
        st.caption(
            "Fontes processadas: " + ", ".join(sorted(str(value) for value in frame["source_file"].unique()))
        )


def run_app_safely(render: Callable[[], None], show_error: Callable[[str], object]) -> None:
    try:
        render()
    except Exception:
        logging.exception("Unexpected dashboard failure")
        show_error("Ocorreu um erro inesperado ao carregar o painel.")


if __name__ == "__main__":
    run_app_safely(main, st.error)
