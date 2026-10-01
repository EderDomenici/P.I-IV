# Martinopolis Revenue Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Streamlit dashboard that downloads and traces real Martinopolis revenue data for 2021–2025, imports optional partial 2026 data, validates accounting aggregation, compares equivalent periods, and presents a simple forecast with temporal MAE evaluation.

**Architecture:** A small Python application separates source acquisition, normalization, validation, analysis, forecasting, and Streamlit presentation. Official statewide TCE-SP ZIP files are streamed and reduced to raw Martinopolis extracts; normalized Parquet and JSON validation artifacts are reproducible outputs. The dashboard reads only validated outputs and never performs source interpretation inside UI code.

**Tech Stack:** Python 3.12-compatible code, Pandas, PyArrow/Parquet, Plotly, Streamlit, openpyxl, xlrd, pytest.

**Spec:** `docs/superpowers/specs/2026-09-28-martinopolis-revenue-dashboard-design.md`

## Global Constraints

- This is a local academic MVP; do not add authentication, an API, a separate frontend, a database, Docker, CI/CD, hosting, monitoring, or production deployment.
- Use official TCE-SP revenue data for 2021–2025; show 2026 only after importing a real partial-period file.
- Do not ship or display synthetic municipal values.
- Preserve source values and row traceability; never silently infer ambiguous accounting meanings.
- Never sum accounting aggregate rows together with their descendants.
- Keep negative revenue values and legitimate reversals.
- Compare partial years only against the same month window in prior years.
- Forecast evaluation must be chronological, must not shuffle observations, and must show the method, holdout window, horizon, and MAE.
- Use Portuguese for the dashboard and README; use English for code, code identifiers, comments, planning documents, and technical specifications.
- Unexpected errors must be logged; expected data failures must become structured validation results and clear Portuguese UI messages.
- The current workspace contains an empty read-only `.git` directory and is not a valid Git repository. Implementation commits are blocked until repository metadata is made writable or the project is moved into a normal Git worktree; do not claim commits were created in the current state.

## Review Focus

- A TCE archive encoded as Windows-1252 or UTF-8 must be read correctly without loading the 500 MB expanded CSV fully into memory; Task 2 pins both encoding detection and chunked filtering.
- A manual file with an absent or ambiguous period/cumulative-value meaning must be rejected with the file name and corrective action; Task 3 pins this behavior.
- Repeated source IDs or mixed aggregate/detail manual rows must never inflate totals; Task 4 pins duplicate detection and leaf-only selection.
- A partial year ending in August must compare only January–August across every selected year; Task 5 pins equivalent-period truncation.
- A forecast series with a missing month or fewer than 36 complete months must be rejected instead of interpolated; Task 6 pins forecast eligibility.

---

## File Map

| Path | Responsibility |
| --- | --- |
| `pyproject.toml` | Python version, dependencies, and pytest configuration |
| `.gitignore` | Ignore virtual environments, caches, full TCE ZIPs, and generated artifacts while retaining filtered raw extracts |
| `src/receitas/__init__.py` | Package marker and public package version |
| `src/receitas/config.py` | Paths, municipality identity, source URLs, and category rules |
| `src/receitas/models.py` | Immutable metadata, issue, report, and forecast result dataclasses |
| `src/receitas/errors.py` | Typed expected application errors |
| `src/receitas/acquisition.py` | Download, checksum, archive inspection, municipality filtering, and source metadata |
| `src/receitas/importers.py` | TCE and manual CSV/XLS/XLSX normalization into the canonical schema |
| `src/receitas/validation.py` | Duplicate, period, hierarchy, cumulative, and indicator-readiness validation |
| `src/receitas/categories.py` | Deterministic category classification without modifying source descriptions |
| `src/receitas/analysis.py` | Summary metrics, monthly series, composition, and equivalent-period comparisons |
| `src/receitas/forecast.py` | Eligibility, seasonal-naive/trailing-mean prediction, holdout MAE, and winner selection |
| `src/receitas/pipeline.py` | End-to-end preparation and artifact writing |
| `scripts/download_tce_data.py` | CLI entry point for official 2021–2025 acquisition |
| `scripts/prepare_data.py` | CLI entry point for normalization, validation, and Parquet/report generation |
| `app.py` | Streamlit page composition and Portuguese user messages |
| `tests/` | Focused unit and integration tests using small fixtures only |
| `data/raw/tce/` | Original-valued Martinopolis extracts from official TCE sources |
| `data/raw/manual/` | Optional user-provided 2026 files |
| `data/metadata/` | Source URL, timestamp, checksum, year, encoding, and row-count JSON |
| `data/processed/` | Reproducible normalized Parquet and validation JSON |
| `docs/receivables-analysis.planning` | Objective, context, steps, decisions, and open questions |
| `docs/data-validation.md` | Generated real-data validation and reconciliation report |
| `README.md` | Portuguese reproduction and usage guide |

### Task 1: Project Foundation and Typed Contracts

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/receitas/__init__.py`
- Create: `src/receitas/config.py`
- Create: `src/receitas/models.py`
- Create: `src/receitas/errors.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: no earlier application interfaces.
- Produces: `SourceSpec`, `SourceMetadata`, `ValidationIssue`, `ValidationReport`, `SummaryMetrics`, `ForecastResult`, `ForecastCandidate`, `PreparationResult`, `DataImportError`, `ValidationBlockedError`, `TCE_SOURCES`, `MUNICIPALITY_NAME`, and canonical path constants.

- [ ] **Step 1: Write tests for immutable contracts and severity behavior**

```python
from dataclasses import FrozenInstanceError

import pytest

from receitas.models import ValidationIssue, ValidationReport


def test_validation_report_is_blocked_only_by_error() -> None:
    warning = ValidationIssue(
        code="PARTIAL_YEAR",
        severity="warning",
        message="2026 contains data through August.",
        context={"year": 2026, "last_month": 8},
    )
    error = ValidationIssue(
        code="AMBIGUOUS_PERIOD",
        severity="error",
        message="The value semantics are unknown.",
        context={"file": "2026.xlsx"},
    )

    assert ValidationReport((warning,)).is_blocked is False
    assert ValidationReport((warning, error)).is_blocked is True


def test_validation_issue_is_immutable() -> None:
    issue = ValidationIssue("X", "warning", "message", {})

    with pytest.raises(FrozenInstanceError):
        issue.code = "Y"  # type: ignore[misc]
```

- [ ] **Step 2: Run the contract tests and verify the expected import failure**

Run: `python -m pytest tests/test_models.py -v`

Expected: FAIL because `receitas.models` does not exist.

- [ ] **Step 3: Create packaging, dependencies, and test configuration**

Create `pyproject.toml` with:

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "receitas-martinopolis"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pandas>=2.2,<3",
  "pyarrow>=17,<22",
  "plotly>=5.24,<7",
  "streamlit>=1.40,<2",
  "openpyxl>=3.1,<4",
  "xlrd>=2.0,<3",
]

[project.optional-dependencies]
dev = ["pytest>=8,<10"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `.gitignore` with `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`, `data/cache/`, `data/processed/*.parquet`, and `data/processed/*.json`. Do not ignore `data/raw/tce/*.csv` or `data/metadata/*.json`.

- [ ] **Step 4: Implement typed models and errors**

Use frozen dataclasses. `ValidationIssue.severity` must be `Literal["warning", "error"]`; `ValidationReport.is_blocked` returns `True` when at least one issue has severity `error`. `SummaryMetrics` contains `collected`, `updated_forecast`, and `realized_percentage` as optional `Decimal` values. `ForecastResult` contains `method`, `mae`, `holdout_start`, `holdout_end`, `horizon_start`, `horizon_end`, `observed`, and `estimated`, with both series typed as `pandas.Series`. `ForecastCandidate` contains `category` and `series`. `PreparationResult` contains `parquet_path`, `validation_json_path`, `validation_markdown_path`, and `report`.

Configure these source URLs exactly:

```python
TCE_SOURCES = {
    year: f"https://transparencia.tce.sp.gov.br/sites/default/files/"
          f"conjunto-dados/receitas-{year}.zip"
    for year in range(2021, 2026)
}
MUNICIPALITY_NAME = "Martinópolis"
```

Define `DataImportError` with `file_name`, `reason`, and `action` attributes and a stable Portuguese `user_message` property. Define `ValidationBlockedError` with a `ValidationReport` attribute.

- [ ] **Step 5: Run the foundation tests**

Run: `python -m pytest tests/test_models.py -v`

Expected: 2 tests PASS.

- [ ] **Step 6: Record the task commit when Git becomes available**

```bash
git add pyproject.toml .gitignore src/receitas tests/test_models.py
git commit -m "chore: scaffold revenue analysis project"
```

Expected in the current workspace: blocked by the invalid read-only `.git`; record the task as implemented but uncommitted rather than claiming success.

### Task 2: Official TCE Acquisition and Raw Traceability

**Files:**
- Create: `src/receitas/acquisition.py`
- Create: `scripts/download_tce_data.py`
- Create: `tests/test_acquisition.py`
- Create: `tests/fixtures/tce_sample_cp1252.csv`

**Interfaces:**
- Consumes: `SourceSpec`, `SourceMetadata`, `TCE_SOURCES`, `MUNICIPALITY_NAME`, and path constants from Task 1.
- Produces: `sha256_file(path: Path) -> str`, `detect_encoding(sample: bytes) -> str`, `filter_tce_archive(archive_path: Path, output_path: Path, municipality: str) -> SourceMetadata`, and `download_all(years: Sequence[int]) -> tuple[SourceMetadata, ...]`.

- [ ] **Step 1: Create a small Windows-1252 fixture and failing acquisition tests**

The fixture must use the actual 2025 header:

```text
id_rec_arrec_detalhe;ano_exercicio;ds_municipio;ds_orgao;mes_referencia;mes_ref_extenso;ds_poder;ds_fonte_recurso;ds_cd_aplicacao_fixo;ds_cd_aplicacao_variavel;ds_categoria;ds_subcategoria;ds_fonte;ds_d1;ds_dd2;ds_d3;ds_tipo;vl_arrecadacao
```

Include two Martinopolis rows and one Adamantina row, encode the file as Windows-1252, and ZIP it inside the test using `zipfile.ZipFile`.

```python
def test_filter_tce_archive_keeps_only_martinopolis_and_original_columns(tmp_path: Path) -> None:
    archive = build_test_archive(tmp_path, encoding="cp1252")
    output = tmp_path / "martinopolis-2025.csv"

    metadata = filter_tce_archive(archive, output, "Martinópolis")
    frame = pd.read_csv(output, sep=";", encoding="utf-8", dtype=str)

    assert frame["ds_municipio"].tolist() == ["Martinópolis", "Martinópolis"]
    assert frame.columns.tolist() == ACTUAL_TCE_COLUMNS
    assert metadata.row_count == 2
    assert metadata.source_encoding == "cp1252"


def test_filter_tce_archive_streams_in_chunks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[int | None] = []
    original = pd.read_csv

    def tracked_read_csv(*args: object, **kwargs: object) -> object:
        calls.append(kwargs.get("chunksize"))
        return original(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", tracked_read_csv)
    filter_tce_archive(build_test_archive(tmp_path), tmp_path / "out.csv", "Martinópolis")

    assert calls and calls[0] == 100_000
```

Also test UTF-8 input, missing `ds_municipio`, no matching rows, SHA-256 stability, and source metadata JSON round-trip.

- [ ] **Step 2: Run acquisition tests and verify failure**

Run: `python -m pytest tests/test_acquisition.py -v`

Expected: FAIL because acquisition functions do not exist.

- [ ] **Step 3: Implement bounded-memory archive filtering**

Open the single CSV member with `zipfile.ZipFile`, detect UTF-8 before Windows-1252 from a byte sample, and call `pandas.read_csv` with `sep=";"`, `dtype=str`, `chunksize=100_000`, and the detected encoding. Validate the actual header before writing. Filter with exact Unicode equality on `ds_municipio`, then write UTF-8 semicolon-separated rows without an index. Preserve every source column and value; add no normalized columns to the raw extract.

Raise `DataImportError` for multiple CSV members, a missing municipality column, or zero matching rows. The error action must say what the user can inspect or correct.

- [ ] **Step 4: Implement download and metadata writing**

Use `urllib.request.urlopen` and copy response bytes in 1 MiB blocks into `data/cache/receitas-{year}.zip`. Never disable TLS verification. Write downloads through a `.part` file and rename only after success. Metadata JSON must contain:

```json
{
  "source_url": "https://transparencia.tce.sp.gov.br/sites/default/files/conjunto-dados/receitas-2025.zip",
  "source_year": 2025,
  "retrieved_at": "ISO-8601 UTC timestamp",
  "source_checksum_sha256": "hex digest",
  "filtered_checksum_sha256": "hex digest",
  "source_encoding": "cp1252",
  "row_count": 2,
  "raw_file": "data/raw/tce/martinopolis-receitas-2025.csv"
}
```

The CLI accepts repeated `--year` values restricted to 2021–2025 and defaults to all five years.

- [ ] **Step 5: Run acquisition tests**

Run: `python -m pytest tests/test_acquisition.py -v`

Expected: all acquisition tests PASS without network access.

- [ ] **Step 6: Record the task commit when Git becomes available**

```bash
git add src/receitas/acquisition.py scripts/download_tce_data.py tests/test_acquisition.py tests/fixtures/tce_sample_cp1252.csv
git commit -m "feat: acquire traceable TCE revenue extracts"
```

### Task 3: Canonical Normalization and Manual Import

**Files:**
- Create: `src/receitas/importers.py`
- Create: `tests/test_importers.py`
- Create: `tests/fixtures/manual_2026_period.csv`
- Create: `tests/fixtures/manual_2026_ambiguous.csv`

**Interfaces:**
- Consumes: filtered TCE CSVs and `DataImportError`.
- Produces: `CANONICAL_COLUMNS`, `parse_brazilian_decimal(value: object) -> Decimal | None`, `normalize_tce_file(path: Path) -> pd.DataFrame`, `normalize_manual_file(path: Path, value_semantics: Literal["period", "cumulative"] | None) -> pd.DataFrame`, and `to_period_values(frame: pd.DataFrame) -> pd.DataFrame`.

- [ ] **Step 1: Write failing parser and TCE normalization tests**

```python
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", Decimal("1234.56")),
        ("-98,10", Decimal("-98.10")),
        ("R$ 0,00", Decimal("0.00")),
        ("", None),
        (None, None),
    ],
)
def test_parse_brazilian_decimal(raw: object, expected: Decimal | None) -> None:
    assert parse_brazilian_decimal(raw) == expected


def test_normalize_tce_file_builds_monthly_detail_rows(tmp_path: Path) -> None:
    path = write_tce_fixture(tmp_path)

    result = normalize_tce_file(path)

    assert result.loc[0, "period"] == pd.Period("2025-01", freq="M")
    assert result.loc[0, "revenue_code"] == "11215001"
    assert result.loc[0, "collected_period"] == Decimal("767.79")
    assert result.loc[0, "is_aggregate"] == False  # noqa: E712
    assert result.loc[0, "source_file"] == path.name
```

Test that source codes remain strings, leading zeros are retained, and negative values survive.

- [ ] **Step 2: Write failing manual-import safety tests**

```python
def test_manual_import_rejects_ambiguous_value_semantics(tmp_path: Path) -> None:
    path = copy_fixture("manual_2026_ambiguous.csv", tmp_path)

    with pytest.raises(DataImportError) as captured:
        normalize_manual_file(path, value_semantics=None)

    assert path.name in captured.value.user_message
    assert "informe se os valores são do período ou acumulados" in captured.value.user_message


def test_cumulative_conversion_does_not_cross_missing_month() -> None:
    frame = cumulative_frame(months=[1, 3], values=[Decimal("100"), Decimal("160")])

    with pytest.raises(DataImportError, match="missing monthly period"):
        to_period_values(frame)
```

Also cover `.xlsx` dispatch, unsupported suffixes, invalid currency, and cumulative negative adjustments.

- [ ] **Step 3: Run importer tests and verify failure**

Run: `python -m pytest tests/test_importers.py -v`

Expected: FAIL because `receitas.importers` does not exist.

- [ ] **Step 4: Implement the canonical schema and TCE mapping**

Map the observed TCE columns as follows:

```python
TCE_COLUMN_MAP = {
    "ano_exercicio": "fiscal_year",
    "mes_referencia": "month",
    "ds_fonte_recurso": "resource_source",
    "ds_cd_aplicacao_fixo": "application_fixed",
    "ds_cd_aplicacao_variavel": "application_variable",
    "vl_arrecadacao": "collected_period",
}
```

Extract `revenue_code` and `revenue_description` from `ds_tipo` by splitting once on `" - "`. Preserve every `ds_*` hierarchy field as `source_hierarchy_*` columns. Set `hierarchy_level="detail"`, `is_aggregate=False`, `collected_cumulative=None`, and both budget forecast fields to null because the TCE source does not publish them.

- [ ] **Step 5: Implement explicit manual-column aliases and cumulative conversion**

Accept normalized aliases for Portuguese headings such as `ano`, `mes`, `competencia`, `codigo`, `especificacao`, `fonte`, `codigo_aplicacao`, `previsao_inicial`, `previsao_atualizada`, `arrecadado_periodo`, and `arrecadado_acumulado`. Reject a file when required period/code/description/value fields cannot be identified uniquely.

For cumulative input, group by the complete accounting identity, sort by month, require consecutive months, and use `groupby(...).diff()` with January equal to its cumulative value. Preserve negative differences.

- [ ] **Step 6: Run importer tests**

Run: `python -m pytest tests/test_importers.py -v`

Expected: all importer tests PASS.

- [ ] **Step 7: Record the task commit when Git becomes available**

```bash
git add src/receitas/importers.py tests/test_importers.py tests/fixtures/manual_2026_period.csv tests/fixtures/manual_2026_ambiguous.csv
git commit -m "feat: normalize TCE and manual revenue files"
```

### Task 4: Validation, Hierarchy Safety, and Revenue Categories

**Files:**
- Create: `src/receitas/validation.py`
- Create: `src/receitas/categories.py`
- Create: `tests/test_validation.py`
- Create: `tests/test_categories.py`

**Interfaces:**
- Consumes: canonical frames from Task 3 and validation models from Task 1.
- Produces: `validate_dataset(frame: pd.DataFrame) -> ValidationReport`, `select_indicator_rows(frame: pd.DataFrame) -> pd.DataFrame`, `classify_revenue(code: str, description: str) -> str`, and `apply_categories(frame: pd.DataFrame) -> pd.DataFrame`.

- [ ] **Step 1: Write failing duplicate and hierarchy tests**

```python
def test_duplicate_source_id_blocks_dataset() -> None:
    frame = canonical_frame(source_row=["10", "10"], collected=[100, 100])

    report = validate_dataset(frame)

    assert report.is_blocked
    assert any(issue.code == "DUPLICATE_SOURCE_ROW" for issue in report.issues)


def test_select_indicator_rows_excludes_aggregate_ancestors() -> None:
    frame = canonical_frame(
        revenue_code=["17000000", "17115101"],
        is_aggregate=[True, False],
        collected=[1000, 600],
    )

    selected = select_indicator_rows(frame)

    assert selected["revenue_code"].tolist() == ["17115101"]
    assert selected["collected_period"].sum() == 600
```

Also test invalid month, missing periods per forecast candidate, partial-year warning, multiple years in one declared manual file, and TCE rows remaining detail-only.

- [ ] **Step 2: Write failing deterministic category tests**

```python
@pytest.mark.parametrize(
    ("code", "description", "expected"),
    [
        ("11125001", "IPTU - Principal", "IPTU"),
        ("11145111", "ISS - Principal", "ISS"),
        ("11130311", "IRRF - Trabalho", "IRRF"),
        ("17115111", "Cota-Parte do FPM", "FPM"),
        ("17215001", "Cota-Parte do ICMS", "ICMS"),
        ("17215101", "Cota-Parte do IPVA", "IPVA"),
        ("17515001", "Transferências do FUNDEB", "FUNDEB"),
        ("17135001", "Transferências de Recursos do SUS", "Saúde"),
        ("99999999", "Receita não mapeada", "Não classificada"),
    ],
)
def test_classify_revenue(code: str, description: str, expected: str) -> None:
    assert classify_revenue(code, description) == expected
```

Add description-based tests for water and sewage only when their explicit terms are present. Test that `Other revenue` is assigned only by the composition function after principal categories are chosen, never by the classifier.

- [ ] **Step 3: Run validation and category tests and verify failure**

Run: `python -m pytest tests/test_validation.py tests/test_categories.py -v`

Expected: FAIL because validation and category modules do not exist.

- [ ] **Step 4: Implement validation rules with structured issues**

Validation must emit stable issue codes and contexts. Errors include missing canonical columns, duplicate `(source_file, source_row)`, invalid months, ambiguous hierarchy, mixed period/cumulative semantics, and missing source traceability. Warnings include partial years, unclassified codes, absent budget forecasts, and missing optional source/application fields.

`select_indicator_rows` accepts all TCE detail rows. For manual data, it selects `is_aggregate=False`; if that flag is unresolved, it raises `ValidationBlockedError` rather than summing.

- [ ] **Step 5: Implement ordered category rules**

Apply exact or prefix code rules before normalized description rules. Keep rules ordered from specific to general. Store the original description untouched and add only the analytical `category` column. Return `Não classificada` for ambiguity.

- [ ] **Step 6: Run validation and category tests**

Run: `python -m pytest tests/test_validation.py tests/test_categories.py -v`

Expected: all tests PASS.

- [ ] **Step 7: Record the task commit when Git becomes available**

```bash
git add src/receitas/validation.py src/receitas/categories.py tests/test_validation.py tests/test_categories.py
git commit -m "feat: validate accounting rows and classify revenues"
```

### Task 5: Analysis and Equivalent-Period Comparisons

**Files:**
- Create: `src/receitas/analysis.py`
- Create: `tests/test_analysis.py`

**Interfaces:**
- Consumes: validated, categorized, indicator-safe frames from Task 4.
- Produces: `summary_metrics(frame: pd.DataFrame) -> SummaryMetrics`, `monthly_series(frame: pd.DataFrame) -> pd.DataFrame`, `revenue_composition(frame: pd.DataFrame, top_n: int = 9) -> pd.DataFrame`, and `equivalent_period_comparison(frame: pd.DataFrame, years: Sequence[int]) -> pd.DataFrame`.

- [ ] **Step 1: Write failing summary and budget-absence tests**

```python
def test_summary_metrics_does_not_invent_missing_budget() -> None:
    frame = canonical_frame(collected=[Decimal("100"), Decimal("50")], updated_forecast=[None, None])

    metrics = summary_metrics(frame)

    assert metrics.collected == Decimal("150")
    assert metrics.updated_forecast is None
    assert metrics.realized_percentage is None
```

- [ ] **Step 2: Write failing equivalent-period and composition tests**

```python
def test_equivalent_period_comparison_truncates_all_years_to_partial_window() -> None:
    frame = monthly_fixture(year_month_limits={2024: 12, 2025: 12, 2026: 8})

    result = equivalent_period_comparison(frame, [2024, 2025, 2026])

    assert result["comparison_last_month"].unique().tolist() == [8]
    assert result.groupby("fiscal_year")["month"].max().to_dict() == {2024: 8, 2025: 8, 2026: 8}


def test_composition_groups_only_validated_remainder_as_other() -> None:
    frame = categorized_fixture(categories=["FPM", "ICMS", "Small A", "Small B"])

    result = revenue_composition(frame, top_n=2)

    assert result["category"].tolist() == ["FPM", "ICMS", "Outras receitas"]
    assert result["amount"].sum() == frame["collected_period"].sum()
```

Also test filters, negative adjustments, and grouping by monthly period.

- [ ] **Step 3: Run analysis tests and verify failure**

Run: `python -m pytest tests/test_analysis.py -v`

Expected: FAIL because analysis functions do not exist.

- [ ] **Step 4: Implement analysis functions without UI dependencies**

Use `Decimal` for summary calculations and convert to float only at the Plotly boundary. `equivalent_period_comparison` determines the smallest last available month among selected years and filters every year to months `1..last_month`. It must expose `comparison_last_month` for UI labeling.

`revenue_composition` groups by category, sorts descending, keeps the requested principal categories, and calculates `Outras receitas` as the exact remainder. Preserve a separate drill-down frame so original codes are still inspectable.

- [ ] **Step 5: Run analysis tests**

Run: `python -m pytest tests/test_analysis.py -v`

Expected: all tests PASS.

- [ ] **Step 6: Record the task commit when Git becomes available**

```bash
git add src/receitas/analysis.py tests/test_analysis.py
git commit -m "feat: add revenue indicators and period comparisons"
```

### Task 6: Simple Forecasting With Temporal Evaluation

**Files:**
- Create: `src/receitas/forecast.py`
- Create: `tests/test_forecast.py`

**Interfaces:**
- Consumes: monthly category series from Task 5 and `ForecastResult` from Task 1.
- Produces: `validate_forecast_series(series: pd.Series, minimum_months: int = 36) -> None`, `seasonal_naive(history: pd.Series, dates: pd.PeriodIndex) -> pd.Series`, `trailing_mean(history: pd.Series, dates: pd.PeriodIndex, window: int = 12) -> pd.Series`, `mean_absolute_error(observed: pd.Series, predicted: pd.Series) -> float`, and `evaluate_and_forecast(series: pd.Series, horizon: int) -> ForecastResult`.

- [ ] **Step 1: Write failing eligibility tests**

```python
def test_forecast_rejects_fewer_than_36_months() -> None:
    series = monthly_series(periods=35)

    with pytest.raises(DataImportError, match="36 complete months"):
        validate_forecast_series(series)


def test_forecast_rejects_missing_month_without_interpolation() -> None:
    series = monthly_series(periods=48).drop(pd.Period("2023-07", freq="M"))

    with pytest.raises(DataImportError, match="missing month"):
        validate_forecast_series(series)
```

- [ ] **Step 2: Write failing method and MAE tests**

```python
def test_seasonal_naive_uses_same_month_of_previous_year() -> None:
    history = deterministic_seasonal_series(start="2021-01", periods=36)
    dates = pd.period_range("2024-01", periods=3, freq="M")

    result = seasonal_naive(history, dates)

    assert result.tolist() == history.loc["2023-01":"2023-03"].tolist()


def test_mean_absolute_error_uses_holdout_observations() -> None:
    observed = pd.Series([100.0, 120.0], index=pd.period_range("2025-01", periods=2, freq="M"))
    predicted = pd.Series([90.0, 140.0], index=observed.index)

    assert mean_absolute_error(observed, predicted) == 15.0


def test_evaluation_selects_lower_mae_and_keeps_estimates_separate() -> None:
    result = evaluate_and_forecast(deterministic_seasonal_series("2021-01", 60), horizon=6)

    assert result.method == "Sazonal ingênuo"
    assert result.observed.index.max() < result.estimated.index.min()
    assert result.holdout_start == pd.Period("2025-01", freq="M")
```

- [ ] **Step 3: Run forecast tests and verify failure**

Run: `python -m pytest tests/test_forecast.py -v`

Expected: FAIL because forecast functions do not exist.

- [ ] **Step 4: Implement chronological holdout evaluation**

Require a unique, monotonically increasing monthly `PeriodIndex`, no missing months, no null values, and at least 36 months. Hold out the last 12 complete months. Evaluate both methods against the same holdout and choose the lower MAE; resolve an exact tie in favor of seasonal naive because it is simpler to explain for monthly public revenue.

For future seasonal-naive predictions, use the same month from the last observed year. For trailing mean, predict one step at a time and append each prediction before calculating the next. Never overwrite or concatenate estimates into the observed series returned to the UI.

- [ ] **Step 5: Run forecast tests**

Run: `python -m pytest tests/test_forecast.py -v`

Expected: all tests PASS.

- [ ] **Step 6: Record the task commit when Git becomes available**

```bash
git add src/receitas/forecast.py tests/test_forecast.py
git commit -m "feat: add evaluated statistical revenue forecast"
```

### Task 7: Reproducible Pipeline and Validation Artifacts

**Files:**
- Create: `src/receitas/pipeline.py`
- Create: `scripts/prepare_data.py`
- Create: `tests/test_pipeline.py`
- Create: `data/raw/tce/.gitkeep`
- Create: `data/raw/manual/.gitkeep`
- Create: `data/metadata/.gitkeep`
- Create: `data/processed/.gitkeep`

**Interfaces:**
- Consumes: acquisition, importer, category, validation, analysis, and forecast interfaces from Tasks 2–6.
- Produces: `prepare_dataset(raw_paths: Sequence[Path], output_dir: Path, validation_markdown_path: Path) -> PreparationResult`, `revenues.parquet`, `validation-report.json`, and `docs/data-validation.md`.

- [ ] **Step 1: Write a failing end-to-end fixture test**

```python
def test_prepare_dataset_writes_traceable_artifacts(tmp_path: Path) -> None:
    raw_paths = write_multi_year_raw_fixtures(tmp_path, years=range(2021, 2026))

    result = prepare_dataset(
        raw_paths,
        tmp_path / "processed",
        tmp_path / "data-validation.md",
    )
    frame = pd.read_parquet(result.parquet_path)
    report = json.loads(result.validation_json_path.read_text(encoding="utf-8"))

    assert set(frame["fiscal_year"]) == {2021, 2022, 2023, 2024, 2025}
    assert frame[["source_file", "source_row"]].notna().all().all()
    assert report["blocked"] is False
    assert result.validation_markdown_path.exists()
```

Add a blocked-case test proving no Parquet is published when duplicate rows or ambiguous hierarchy produce an error.

- [ ] **Step 2: Run pipeline tests and verify failure**

Run: `python -m pytest tests/test_pipeline.py -v`

Expected: FAIL because pipeline functions do not exist.

- [ ] **Step 3: Implement atomic artifact preparation**

Load each raw extract, normalize it, concatenate with `ignore_index=True`, apply categories, validate, and write artifacts through temporary files followed by atomic rename. If `ValidationReport.is_blocked` is true, write only the JSON and Markdown reports and raise `ValidationBlockedError`; do not replace a previously valid Parquet file.

The generated Markdown report must contain these exact sections: `Source inventory`, `Temporal coverage`, `Hierarchy decision`, `Duplicate checks`, `Category coverage`, `Budget availability`, `Forecast eligibility`, `Blocking issues`, and `Warnings`. Populate them from measured data rather than static prose.

- [ ] **Step 4: Implement the preparation CLI**

Support:

```text
python scripts/prepare_data.py
python scripts/prepare_data.py --manual data/raw/manual/receitas-2026.xlsx --value-semantics cumulative
```

Default discovery includes all `data/raw/tce/martinopolis-receitas-*.csv`. A manual path requires `--value-semantics period|cumulative`. Exit code is `0` on success, `2` for expected data validation failure, and `1` for an unexpected logged exception.

- [ ] **Step 5: Run pipeline tests and the complete unit suite**

Run: `python -m pytest tests/test_pipeline.py -v`

Expected: pipeline tests PASS.

Run: `python -m pytest -v`

Expected: all tests PASS.

- [ ] **Step 6: Record the task commit when Git becomes available**

```bash
git add src/receitas/pipeline.py scripts/prepare_data.py tests/test_pipeline.py data
git commit -m "feat: build reproducible revenue data pipeline"
```

### Task 8: Streamlit Dashboard

**Files:**
- Create: `app.py`
- Create: `tests/test_app_helpers.py`

**Interfaces:**
- Consumes: `data/processed/revenues.parquet`, `validation-report.json`, Task 5 analysis functions, and Task 6 forecast functions.
- Produces: a four-tab Portuguese Streamlit interface and pure helper functions `format_brl_currency`, `format_percentage`, `load_dashboard_data`, and `select_forecast_candidate`.

- [ ] **Step 1: Write failing UI-helper tests**

```python
def test_currency_format_uses_brazilian_separators() -> None:
    assert format_brl_currency(Decimal("1234567.89")) == "R$ 1.234.567,89"


def test_select_forecast_candidate_prefers_complete_stable_series() -> None:
    frame = forecast_candidate_fixture(
        complete_category="FPM",
        incomplete_category="ICMS",
    )

    candidate = select_forecast_candidate(frame)

    assert candidate.category == "FPM"
    assert len(candidate.series) == 60
```

Test that missing Parquet produces an actionable Portuguese message and that forecast failure is converted into an informational UI state rather than an exception.

- [ ] **Step 2: Run UI-helper tests and verify failure**

Run: `python -m pytest tests/test_app_helpers.py -v`

Expected: FAIL because `app.py` does not exist.

- [ ] **Step 3: Implement pure UI helpers and cached loading**

Use `@st.cache_data` only around disk loading and deterministic derived frames. Do not perform downloads in the Streamlit process. `load_dashboard_data` validates required processed columns and raises `DataImportError` with instructions to run the download and preparation scripts.

Keep page rendering inside `main()`. Importing `app.py` in tests must not render a page or read project data.

- [ ] **Step 4: Implement the four dashboard tabs**

Create `Visão geral`, `Evolução mensal`, `Comparação entre anos`, and `Previsão e qualidade` tabs. Put year, period, and category filters in the sidebar. Show source and application filters only when those columns are populated consistently.

Use Plotly for monthly lines, category composition, equivalent-period bars, and the observed/estimated forecast line. Observed and estimated traces must have different colors and the estimate must be dashed. Every tab shows its effective covered period. Show `2026 — parcial até <month>` when applicable.

If budget columns are absent, render `Previsão orçamentária não disponível nesta fonte` instead of zero. If forecasting is unavailable, render the exact validation reason and keep the other tabs functional.

- [ ] **Step 5: Run UI tests and start a headless smoke test**

Run: `python -m pytest tests/test_app_helpers.py -v`

Expected: all helper tests PASS.

Run: `timeout 20s python -m streamlit run app.py --server.headless true --server.port 8501`

Expected: Streamlit logs a local URL and starts without a Python traceback; timeout exit code `124` is acceptable after successful startup.

- [ ] **Step 6: Record the task commit when Git becomes available**

```bash
git add app.py tests/test_app_helpers.py
git commit -m "feat: add municipal revenue dashboard"
```

### Task 9: Real Data, Documentation, and Final Verification

**Files:**
- Create: `README.md`
- Create: `docs/receivables-analysis.planning`
- Modify: `docs/data-validation.md` through the pipeline using real data
- Create: `data/raw/tce/martinopolis-receitas-2021.csv`
- Create: `data/raw/tce/martinopolis-receitas-2022.csv`
- Create: `data/raw/tce/martinopolis-receitas-2023.csv`
- Create: `data/raw/tce/martinopolis-receitas-2024.csv`
- Create: `data/raw/tce/martinopolis-receitas-2025.csv`
- Create: `data/metadata/receitas-2021.json` through `data/metadata/receitas-2025.json`

**Interfaces:**
- Consumes: the complete application and all official TCE source URLs.
- Produces: a reproducible real-data academic project with verified instructions and measured validation documentation.

- [ ] **Step 1: Download and filter the five official datasets**

Run: `python scripts/download_tce_data.py --year 2021 --year 2022 --year 2023 --year 2024 --year 2025`

Expected: five UTF-8 raw extracts contain only `ds_municipio == "Martinópolis"`; five JSON metadata files contain official source URLs, timestamps, checksums, encodings, and positive row counts. Full ZIPs remain under ignored `data/cache/` only.

- [ ] **Step 2: Prepare and inspect the real dataset**

Run: `python scripts/prepare_data.py`

Expected: `data/processed/revenues.parquet`, `data/processed/validation-report.json`, and `docs/data-validation.md` are generated. If validation blocks publication, inspect the measured issue, adjust only an evidence-backed mapping or rule, add a regression test, and rerun; never suppress or downgrade the issue merely to make the command pass.

- [ ] **Step 3: Write the English planning record**

Create `docs/receivables-analysis.planning` with these sections in order:

```markdown
# Objective
# Context
# Steps
# Decisions
# Open questions
```

Record the chosen TCE source, Streamlit architecture, no-database decision, observed TCE schema, detail-row aggregation decision, actual category coverage, forecast candidate, and any remaining 2026 manual-data dependency. Do not state that 2026 is implemented when no real 2026 file exists.

- [ ] **Step 4: Write the Portuguese README**

Include prerequisites, virtual-environment commands, `pip install -e .[dev]`, official source attribution, acquisition and preparation commands, optional 2026 import examples for both value semantics, `streamlit run app.py`, test commands, directory roles, forecast method, MAE explanation, data limitations, and a statement that the dashboard does not identify irregularities or replace accounting analysis.

- [ ] **Step 5: Run full automated verification**

Run: `python -m pytest -v`

Expected: all tests PASS.

Run: `python scripts/prepare_data.py`

Expected: exit code `0` with real 2021–2025 data and a non-blocked report.

Run: `timeout 20s python -m streamlit run app.py --server.headless true --server.port 8501`

Expected: successful startup with no traceback before timeout.

- [ ] **Step 6: Perform browser-level dashboard validation**

Open `http://127.0.0.1:8501` and verify:

- 2021–2025 are selectable and the covered period is visible;
- no 2026 option appears without a real manual file;
- summary totals match a direct Pandas aggregation of indicator-safe rows;
- composition totals reconcile to the filtered summary total;
- equivalent-period comparison labels the common month window;
- observed and estimated forecast traces are visually distinct;
- method, holdout period, horizon, and MAE appear beside the forecast;
- the data-quality tab lists source files and validation limitations;
- narrow viewport content remains readable without horizontal page overflow.

- [ ] **Step 7: Record the final commit when Git becomes available**

```bash
git add README.md docs data/raw/tce data/metadata
git commit -m "docs: add real data provenance and reproduction guide"
```

Do not add ignored full ZIPs or generated Parquet artifacts to Git.

## Final Review Gate

After all tasks pass, review the implementation against every completion criterion in the design spec. Report separately:

- implemented application behavior;
- real-data coverage and measured limitations;
- automated test results;
- dashboard/browser verification;
- Git status, explicitly noting whether repository initialization remained blocked.

Do not call the project complete if source reconciliation is blocked, forecast evaluation leaks future data, 2026 is presented without a real file, or dashboard totals cannot be traced back to raw source rows.
