from decimal import Decimal

import pandas as pd
import pytest

from receitas.errors import ValidationBlockedError
from receitas.validation import select_indicator_rows, validate_dataset


def canonical_frame(**overrides: object) -> pd.DataFrame:
    base: dict[str, object] = {
        "period": [pd.Period("2025-01", freq="M"), pd.Period("2025-02", freq="M")],
        "fiscal_year": [2025, 2025],
        "month": [1, 2],
        "revenue_code": ["11125001", "11125001"],
        "revenue_description": ["IPTU", "IPTU"],
        "category": ["IPTU", "IPTU"],
        "resource_source": ["Tesouro", "Tesouro"],
        "application_code": ["Geral", "Geral"],
        "initial_forecast": [None, None],
        "updated_forecast": [None, None],
        "collected_period": [Decimal("100"), Decimal("120")],
        "collected_cumulative": [None, None],
        "hierarchy_level": ["detail", "detail"],
        "is_aggregate": [False, False],
        "source_file": ["2025.csv", "2025.csv"],
        "source_row": ["1", "2"],
        "source_kind": ["tce", "tce"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_duplicate_source_id_blocks_dataset() -> None:
    frame = canonical_frame(source_row=["10", "10"])

    report = validate_dataset(frame)

    assert report.is_blocked
    assert any(issue.code == "DUPLICATE_SOURCE_ROW" for issue in report.issues)


def test_select_indicator_rows_excludes_aggregate_ancestors() -> None:
    frame = canonical_frame(
        revenue_code=["17000000", "17115101"],
        is_aggregate=[True, False],
        collected_period=[Decimal("1000"), Decimal("600")],
    )

    selected = select_indicator_rows(frame)

    assert selected["revenue_code"].tolist() == ["17115101"]
    assert selected["collected_period"].sum() == Decimal("600")


def test_unknown_manual_hierarchy_blocks_indicator_selection() -> None:
    frame = canonical_frame(source_kind=["manual", "manual"], is_aggregate=[pd.NA, pd.NA])

    with pytest.raises(ValidationBlockedError):
        select_indicator_rows(frame)


def test_partial_year_and_absent_budget_are_warnings() -> None:
    report = validate_dataset(canonical_frame())

    assert report.is_blocked is False
    codes = {issue.code for issue in report.issues}
    assert "PARTIAL_YEAR" in codes
    assert "BUDGET_UNAVAILABLE" in codes


def test_invalid_month_blocks_dataset() -> None:
    report = validate_dataset(canonical_frame(month=[1, 13]))

    assert report.is_blocked
    assert any(issue.code == "INVALID_MONTH" for issue in report.issues)
