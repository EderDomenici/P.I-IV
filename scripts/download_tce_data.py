#!/usr/bin/env python3
from __future__ import annotations

import argparse

from receitas.acquisition import download_all
from receitas.config import MUNICIPALITY_NAME, TCE_SOURCES
from receitas.errors import DataImportError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Baixa receitas oficiais do TCE-SP.")
    parser.add_argument(
        "--year",
        action="append",
        type=int,
        choices=sorted(TCE_SOURCES),
        dest="years",
        help="Ano a baixar; pode ser repetido. O padrão baixa 2021–2025.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = args.years or sorted(TCE_SOURCES)
    try:
        results = download_all(years, municipality=MUNICIPALITY_NAME)
    except DataImportError as error:
        print(error.user_message)
        return 2
    for metadata in results:
        print(f"{metadata.source_year}: {metadata.row_count} linhas -> {metadata.raw_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
