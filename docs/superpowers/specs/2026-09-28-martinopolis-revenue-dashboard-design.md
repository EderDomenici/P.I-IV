# Martinopolis Revenue Dashboard — Design Specification

## Objective

Build a small, local, reproducible academic application that turns official
Martinopolis municipal revenue records into an interactive dashboard. The
application must support historical analysis, equivalent-period comparisons,
and a simple statistically evaluated forecast without presenting estimates as
facts or implying automated auditing.

## Context

The repository currently contains the implementation guide but no application
code or municipal revenue files. Official annual revenue datasets for 2021
through 2025 are available from the Sao Paulo State Court of Accounts (TCE-SP).
The 2026 period will only be displayed after a real partial-year file is
provided through the manual importer.

This is an academic project with no intended production deployment. The design
therefore excludes authentication, a separate API, a separate frontend, a
database, containers, cloud infrastructure, and production-grade operational
concerns.

## Scope

### Included

- Download and filter official TCE-SP annual revenue datasets for 2021–2025.
- Preserve the unmodified Martinopolis rows extracted from each source file.
- Record source URL, source year, download timestamp, checksum, and import
  metadata.
- Import an optional 2026 partial-period file in CSV, XLS, or XLSX format.
- Inspect and normalize codes, descriptions, accounting periods, sources,
  applications, budget forecasts, and collected amounts when present.
- Validate duplicates, temporal coverage, accounting hierarchy, and aggregate
  consistency before publishing indicators.
- Show overview, monthly evolution, revenue composition, and equivalent-period
  comparisons in a local Streamlit dashboard.
- Compare two simple forecast methods using an out-of-sample temporal test and
  display the winning method's MAE.
- Document data limitations and prevent unsupported calculations from being
  shown.

### Excluded

- Expenses, contracts, procurement, payroll, or automated auditing.
- Automatic anomaly or irregularity detection in the first MVP.
- Mandatory automatic collection from the Martinopolis municipal portal.
- Authentication, authorization, user management, or sensitive data handling.
- FastAPI, a JavaScript frontend, relational databases, Docker, CI/CD, hosting,
  monitoring, or production deployment.
- Machine-learning libraries and complex forecasting models.

## Technology Choice

- Python 3.12 or another currently installed compatible Python 3 version.
- Pandas for ingestion, normalization, aggregation, and validation.
- PyArrow and Parquet for compact, typed processed datasets.
- Plotly for interactive charts.
- Streamlit for the local interface.
- openpyxl and xlrd only for supported manual spreadsheet imports.
- pytest for focused automated tests.

The project will not use scikit-learn. Forecast calculations and MAE are small
enough to implement directly with Pandas and NumPy-compatible operations.

## Proposed Project Structure

```text
app.py
src/
  __init__.py
  config.py
  data_import.py
  validation.py
  analysis.py
  forecast.py
scripts/
  download_tce_data.py
data/
  raw/
    tce/
    manual/
  processed/
  metadata/
tests/
docs/
  receivables-analysis.planning
  data-validation.md
requirements.txt
README.md
```

`app.py` is responsible only for page composition, filters, and presentation.
Business calculations stay in `src/` so they can be tested without Streamlit.

## Data Acquisition and Traceability

### TCE-SP annual data

The download script will obtain the official annual revenue files for
2021–2025. Because the statewide files are large, full downloads are temporary
and are not kept in the repository. For every year, the script will:

1. download the official source to a temporary local file;
2. inspect the actual delimiter, encoding, columns, and municipality key;
3. filter records for Martinopolis using the official municipality identifier
   when available, with normalized-name matching used only as a verified
   fallback;
4. save the filtered rows without renaming or changing source values under
   `data/raw/tce/`;
5. create metadata containing the source URL, source year, retrieval timestamp,
   source-file checksum, filtered-file checksum, and row count.

The filtered raw extract is the project's auditable input. Every normalized
record will retain its source year, source file, and original row identifier or
row number.

### Manual 2026 data

Files placed under `data/raw/manual/` may be CSV, XLS, or XLSX. The importer will
inspect their real columns before mapping them to the normalized schema. A small
explicit mapping configuration will handle known layout differences; it will
not guess ambiguous accounting meanings.

The importer must record the file name, checksum, import timestamp, declared
year, covered months, and whether source values are period values or cumulative
values. If that distinction cannot be established, the file is rejected with
an actionable validation message.

No synthetic municipal data will be shipped or displayed.

## Normalized Data Model

The definitive mapping will be established only after inspecting the downloaded
source schema. The processed dataset will expose the following canonical fields
when supported by the source:

| Field | Purpose |
| --- | --- |
| `period` | Monthly accounting period |
| `fiscal_year` | Fiscal year |
| `month` | Month number |
| `revenue_code` | Original accounting code as text |
| `revenue_description` | Original description |
| `category` | Project-defined analytical category |
| `resource_source` | Source-of-funds label or code |
| `application_code` | Application code |
| `initial_forecast` | Initial budget forecast |
| `updated_forecast` | Updated budget forecast |
| `collected_period` | Amount collected in the period |
| `collected_cumulative` | Reported cumulative amount |
| `hierarchy_level` | Accounting hierarchy level when derivable |
| `is_aggregate` | Whether the record is an aggregate node |
| `source_file` | Raw input file |
| `source_row` | Raw row traceability identifier |
| `source_kind` | `tce` or `manual` |

Currency values will use numeric decimal semantics during normalization. Codes
remain strings to preserve leading zeros. Negative amounts are valid and will
not be discarded.

## Accounting Hierarchy and Double-Counting Prevention

The application must never sum all hierarchy levels together. During source
inspection, the implementation will determine the safest aggregation level by
examining available codes, hierarchy markers, and published totals.

Indicators will only use one documented level or an explicitly validated set of
leaf records. Aggregate rows remain available for reconciliation but are not
combined with their descendants. When the hierarchy cannot be derived reliably,
the validator blocks aggregate indicators and reports the unresolved condition.

Calculated annual totals will be compared with the source's applicable
published totals when the dataset provides them. Material divergence is treated
as a validation failure, not hidden by rounding or manual adjustment.

## Cumulative and Period Values

The importer will explicitly classify monetary columns as period or cumulative
values. Monthly values may be calculated from a cumulative sequence only when:

- all expected periods in the sequence are ordered and identifiable;
- cumulative semantics are confirmed from the source structure;
- differences reconcile back to the reported cumulative values.

Adjustments, reversals, and legitimate negative differences are preserved. A
gap in a cumulative series prevents silent differencing across the gap.

## Revenue Categories

The initial category configuration will test mappings for FPM, ICMS, FUNDEB,
health transfers, ISS, IPVA, IPTU, water, IRRF, and sewage. Mapping rules will be
based on stable accounting codes where possible and documented description
rules otherwise.

Ambiguous codes remain `Unclassified` and are listed for review. `Other revenue`
means the validated remainder after principal categories are selected; it is
not a destructive rewrite of the original classification.

## Dashboard

The Streamlit application will be presented in Brazilian Portuguese and contain
four sections.

### Overview

- covered period and source status;
- collected revenue;
- updated budget forecast when available;
- realized percentage when the numerator and denominator are valid;
- composition of principal revenue categories;
- visible warning when 2026 is absent or partial.

### Monthly evolution

- year, date-range, and category filters;
- source and application filters only when their source columns are consistent;
- monthly line chart using validated period values.

### Equivalent-period comparison

- compare the same available month window across selected years;
- never compare a partial year with full prior years without truncating the
  prior years to the same final month;
- display the effective comparison window in the interface.

### Forecast and data quality

- observed and estimated values shown with different visual styles;
- forecast horizon, selected method, and historical MAE;
- warnings and blocked analyses from the validation report;
- explanation that the forecast is a historical estimate, not a guaranteed
  revenue amount.

The application remains usable when no series qualifies for forecasting. It
shows the reason rather than creating a substitute forecast.

## Forecast Design

Forecasting will use a recurring revenue series with stable classification and
sufficient monthly observations. The initial candidate is selected only after
the real data is profiled.

Two methods will be evaluated:

1. **Seasonal naive:** use the observed value from the same month of the prior
   year.
2. **Trailing mean:** use the mean of a documented trailing window available
   strictly before the predicted month.

Evaluation is chronological. The most recent complete evaluation window is held
out, while all earlier observations form the training history. The exact window
length depends on available complete monthly history and will be reported in the
interface. No random split is permitted.

For each method, the implementation calculates:

```text
MAE = mean(abs(observed - predicted))
```

The method with the lower holdout MAE is used for the displayed future horizon.
Forecast generation must not consume future observations. A series is rejected
when it lacks sufficient seasonal history, contains unresolved classification
breaks, or has missing periods that invalidate the comparison.

## Error Handling

Expected data problems produce typed domain exceptions or structured validation
results instead of raw stack traces in the interface. Messages must identify:

- the affected file or period;
- the failed rule;
- whether the failure blocks all analysis or only a specific indicator;
- the action required to continue.

Unexpected failures are logged with technical context and shown to users as a
short Portuguese error message. Errors are never silently ignored.

## Verification Strategy

Focused pytest tests will cover the rules most likely to create materially wrong
results:

- Brazilian currency parsing and negative values;
- date and accounting-period normalization;
- duplicate export detection;
- cumulative-to-period conversion and gaps;
- hierarchy-level selection and double-count prevention;
- equivalent-period comparison;
- seasonal-naive and trailing-mean forecasts;
- MAE calculation;
- strict separation of observed and estimated values.

Additional verification will run the full data pipeline on the downloaded real
extracts, start the Streamlit application locally, and check that every displayed
total can be traced to source files. The README reproduction steps must work in
a fresh virtual environment.

## Documentation Deliverables

- `README.md`: setup, download/import steps, local execution, expected file
  formats, source attribution, covered periods, and limitations.
- `docs/receivables-analysis.planning`: objective, context, implementation steps,
  decisions, and open questions, written in English.
- `docs/data-validation.md`: chosen hierarchy level, category rules,
  reconciliation results, rejected files, and known limitations.
- Source metadata files under `data/metadata/`.

## Completion Criteria

The MVP is complete when:

1. another person can install dependencies, obtain or use the filtered official
   data, prepare it, and start the dashboard using the README;
2. the dashboard uses real Martinopolis data for 2021–2025;
3. no indicator mixes aggregate accounting rows with their descendants;
4. an optional 2026 dataset is visibly partial and comparisons use equivalent
   month windows;
5. the forecast reports its method, evaluation window, MAE, and horizon, or
   clearly explains why no eligible series exists;
6. focused automated tests pass;
7. source files and dashboard totals remain traceable through metadata and raw
   row identifiers.

## Decisions

- Use Streamlit, Pandas, Plotly, and Parquet.
- Use official TCE-SP data for 2021–2025 and manual import for partial 2026.
- Use no database, API, authentication, deployment infrastructure, or ML
  framework.
- Compare seasonal-naive and trailing-mean forecasting methods using temporal
  holdout MAE.
- Exclude anomaly detection from the initial MVP.
- Prefer blocked output with a documented cause over an unsupported assumption.

## Open Questions

No product decisions remain open. Source-specific column mappings, hierarchy
rules, and the forecast candidate series are implementation findings that must
be resolved from the real downloaded data and recorded in the validation
documentation.
