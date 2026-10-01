from dataclasses import FrozenInstanceError

import pytest

from receitas.errors import DataImportError
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


def test_data_import_error_exposes_actionable_portuguese_message() -> None:
    error = DataImportError(
        file_name="receitas-2026.xlsx",
        reason="sem coluna de competência",
        action="informe o mês de referência",
    )

    assert error.user_message == (
        "Não foi possível importar receitas-2026.xlsx: sem coluna de competência. "
        "Ação necessária: informe o mês de referência."
    )
