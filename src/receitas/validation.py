from __future__ import annotations

import pandas as pd

from receitas.errors import ValidationBlockedError
from receitas.importers import CANONICAL_COLUMNS
from receitas.models import ValidationIssue, ValidationReport


def _issue(
    code: str,
    severity: str,
    message: str,
    **context: object,
) -> ValidationIssue:
    if severity not in {"warning", "error"}:
        raise ValueError(f"Unsupported severity: {severity}")
    return ValidationIssue(code, severity, message, context)  # type: ignore[arg-type]


def validate_dataset(frame: pd.DataFrame) -> ValidationReport:
    issues: list[ValidationIssue] = []
    missing = [column for column in CANONICAL_COLUMNS if column not in frame.columns]
    if missing:
        return ValidationReport(
            (
                _issue(
                    "MISSING_COLUMNS",
                    "error",
                    "The normalized dataset is missing required columns.",
                    columns=missing,
                ),
            )
        )

    duplicate_mask = frame.duplicated(subset=["source_file", "source_row"], keep=False)
    if duplicate_mask.any():
        issues.append(
            _issue(
                "DUPLICATE_SOURCE_ROW",
                "error",
                "The same source row appears more than once.",
                count=int(duplicate_mask.sum()),
            )
        )

    invalid_month = ~frame["month"].between(1, 12)
    if invalid_month.any():
        issues.append(
            _issue(
                "INVALID_MONTH",
                "error",
                "Month values must be between 1 and 12.",
                rows=frame.index[invalid_month].tolist(),
            )
        )

    missing_trace = frame[["source_file", "source_row"]].isna().any(axis=1)
    if missing_trace.any():
        issues.append(
            _issue(
                "MISSING_TRACEABILITY",
                "error",
                "Every normalized row must identify its source file and row.",
                count=int(missing_trace.sum()),
            )
        )

    ambiguous_hierarchy = frame["is_aggregate"].isna()
    if ambiguous_hierarchy.any():
        issues.append(
            _issue(
                "AMBIGUOUS_HIERARCHY",
                "error",
                "Manual rows must be identified as detail or aggregate before analysis.",
                count=int(ambiguous_hierarchy.sum()),
            )
        )

    for year, group in frame.groupby("fiscal_year", sort=True):
        last_month = int(group["month"].max())
        if last_month < 12:
            issues.append(
                _issue(
                    "PARTIAL_YEAR",
                    "warning",
                    "The fiscal year does not contain all twelve months.",
                    year=int(year),
                    last_month=last_month,
                )
            )

    if frame["updated_forecast"].isna().all():
        issues.append(
            _issue(
                "BUDGET_UNAVAILABLE",
                "warning",
                "The source does not provide an updated budget forecast.",
            )
        )

    unclassified = frame["category"].eq("Não classificada")
    if unclassified.any():
        issues.append(
            _issue(
                "UNCLASSIFIED_REVENUE",
                "warning",
                "Some revenue codes do not have an analytical category.",
                count=int(unclassified.sum()),
            )
        )
    return ValidationReport(tuple(issues))


def select_indicator_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if "is_aggregate" not in frame.columns or frame["is_aggregate"].isna().any():
        report = ValidationReport(
            (
                _issue(
                    "AMBIGUOUS_HIERARCHY",
                    "error",
                    "Rows with unresolved hierarchy cannot be aggregated safely.",
                ),
            )
        )
        raise ValidationBlockedError(report)
    return frame.loc[~frame["is_aggregate"].astype(bool)].copy()
