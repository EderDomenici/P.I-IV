from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Literal, Sequence

import pandas as pd

from receitas.categories import apply_categories
from receitas.errors import DataImportError, ValidationBlockedError
from receitas.forecast import validate_forecast_series
from receitas.importers import normalize_manual_file, normalize_tce_file
from receitas.models import PreparationResult, ValidationReport
from receitas.validation import select_indicator_rows, validate_dataset


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _report_payload(report: ValidationReport) -> dict[str, object]:
    return {
        "blocked": report.is_blocked,
        "issues": [asdict(issue) for issue in report.issues],
    }


def _validation_markdown(frame: pd.DataFrame, report: ValidationReport) -> str:
    source_lines = [
        f"- `{file_name}`: {len(group)} rows"
        for file_name, group in frame.groupby("source_file", sort=True)
    ]
    coverage_lines = [
        f"- {int(year)}: months {int(group['month'].min())}–{int(group['month'].max())}, {len(group)} rows"
        for year, group in frame.groupby("fiscal_year", sort=True)
    ]
    category_lines = [
        f"- {category}: {len(group)} rows"
        for category, group in frame.groupby("category", dropna=False, sort=True)
    ]
    duplicate_count = int(frame.duplicated(["source_file", "source_row"], keep=False).sum())
    budget_available = not frame["updated_forecast"].isna().all()
    forecast_lines: list[str] = []
    for category, group in frame.groupby("category", dropna=False, sort=True):
        monthly = group.groupby("period")["collected_period"].apply(
            lambda values: float(sum(values))
        )
        monthly.index = pd.PeriodIndex(monthly.index, freq="M")
        try:
            validate_forecast_series(monthly)
        except DataImportError as error:
            forecast_lines.append(f"- {category}: not eligible — {error.reason}")
        else:
            forecast_lines.append(f"- {category}: eligible ({len(monthly)} complete months)")

    errors = [issue for issue in report.issues if issue.severity == "error"]
    warnings = [issue for issue in report.issues if issue.severity == "warning"]
    error_lines = [f"- `{issue.code}`: {issue.message}" for issue in errors] or ["- None"]
    warning_lines = [f"- `{issue.code}`: {issue.message}" for issue in warnings] or ["- None"]
    hierarchy = (
        "All rows used by indicators are detail rows; aggregate ancestors are excluded."
        if not frame["is_aggregate"].isna().any()
        else "Hierarchy is unresolved and blocks publication."
    )
    return "\n".join(
        [
            "# Data validation",
            "",
            "## Source inventory",
            *source_lines,
            "",
            "## Temporal coverage",
            *coverage_lines,
            "",
            "## Hierarchy decision",
            hierarchy,
            "",
            "## Duplicate checks",
            f"Duplicate source rows: {duplicate_count}.",
            "",
            "## Category coverage",
            *category_lines,
            "",
            "## Budget availability",
            "Updated budget forecast is available."
            if budget_available
            else "The TCE source does not provide updated budget forecasts.",
            "",
            "## Forecast eligibility",
            *(forecast_lines or ["- No category series available"]),
            "",
            "## Blocking issues",
            *error_lines,
            "",
            "## Warnings",
            *warning_lines,
            "",
        ]
    )


def prepare_dataset(
    raw_paths: Sequence[Path],
    output_dir: Path,
    validation_markdown_path: Path,
    manual_value_semantics: Literal["period", "cumulative"] | None = None,
) -> PreparationResult:
    if not raw_paths:
        raise DataImportError(
            "data/raw",
            "nenhum arquivo de receita foi encontrado",
            "execute o script de download ou informe um arquivo manual",
        )
    frames: list[pd.DataFrame] = []
    for path in raw_paths:
        if path.name.startswith("martinopolis-receitas-"):
            frames.append(normalize_tce_file(path))
        else:
            frames.append(normalize_manual_file(path, manual_value_semantics))
    combined = apply_categories(pd.concat(frames, ignore_index=True))
    report = validate_dataset(combined)
    output_dir.mkdir(parents=True, exist_ok=True)
    validation_json_path = output_dir / "validation-report.json"
    _atomic_text(
        validation_json_path,
        json.dumps(_report_payload(report), ensure_ascii=False, indent=2) + "\n",
    )
    _atomic_text(validation_markdown_path, _validation_markdown(combined, report))
    if report.is_blocked:
        raise ValidationBlockedError(report)

    indicator_rows = select_indicator_rows(combined)
    persisted = indicator_rows.copy()
    persisted["period"] = persisted["period"].astype(str)
    parquet_path = output_dir / "revenues.parquet"
    temporary = output_dir / "revenues.parquet.part"
    persisted.to_parquet(temporary, index=False)
    temporary.replace(parquet_path)
    return PreparationResult(
        parquet_path=parquet_path,
        validation_json_path=validation_json_path,
        validation_markdown_path=validation_markdown_path,
        report=report,
    )
