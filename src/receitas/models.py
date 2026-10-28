from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal, Mapping

import pandas as pd


Severity = Literal["warning", "error"]


@dataclass(frozen=True)
class SourceSpec:
    year: int
    url: str


@dataclass(frozen=True)
class SourceMetadata:
    source_url: str
    source_year: int
    retrieved_at: str
    source_checksum_sha256: str
    filtered_checksum_sha256: str
    source_encoding: str
    row_count: int
    raw_file: str


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    context: Mapping[str, object]


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def is_blocked(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)


@dataclass(frozen=True)
class SummaryMetrics:
    collected: Decimal
    updated_forecast: Decimal | None
    realized_percentage: Decimal | None


@dataclass(frozen=True)
class ForecastResult:
    method: str
    mae: float
    mae_by_method: Mapping[str, float]
    holdout_start: pd.Period
    holdout_end: pd.Period
    horizon_start: pd.Period
    horizon_end: pd.Period
    observed: pd.Series
    validation_estimated: pd.Series
    estimated: pd.Series


@dataclass(frozen=True)
class ForecastCandidate:
    category: str
    series: pd.Series


@dataclass(frozen=True)
class PreparationResult:
    parquet_path: Path
    validation_json_path: Path
    validation_markdown_path: Path
    report: ValidationReport
