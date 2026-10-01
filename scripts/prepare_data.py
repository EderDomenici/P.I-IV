#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from receitas.config import PROCESSED_DIR, PROJECT_ROOT, RAW_TCE_DIR
from receitas.errors import DataImportError, ValidationBlockedError
from receitas.pipeline import prepare_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepara os dados do dashboard.")
    parser.add_argument("--manual", type=Path, help="Arquivo CSV/XLS/XLSX parcial de 2026.")
    parser.add_argument(
        "--value-semantics",
        choices=("period", "cumulative"),
        help="Obrigatório com --manual: valores do período ou acumulados.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.manual and not args.value_semantics:
        print("Use --value-semantics period|cumulative junto com --manual.")
        return 2
    paths = sorted(RAW_TCE_DIR.glob("martinopolis-receitas-*.csv"))
    if args.manual:
        paths.append(args.manual)
    try:
        result = prepare_dataset(
            paths,
            PROCESSED_DIR,
            PROJECT_ROOT / "docs" / "data-validation.md",
            manual_value_semantics=args.value_semantics,
        )
    except DataImportError as error:
        print(error.user_message)
        return 2
    except ValidationBlockedError as error:
        print(f"A validação bloqueou a publicação: {len(error.report.issues)} ocorrência(s).")
        return 2
    except Exception:
        logging.exception("Unexpected data preparation failure")
        return 1
    print(f"Dados preparados em {result.parquet_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
