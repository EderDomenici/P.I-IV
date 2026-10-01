from __future__ import annotations

import hashlib
import json
import re
import shutil
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from zipfile import BadZipFile, ZipFile

import pandas as pd

from receitas.config import CACHE_DIR, METADATA_DIR, PROJECT_ROOT, RAW_TCE_DIR, TCE_SOURCES
from receitas.errors import DataImportError
from receitas.models import SourceMetadata


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def detect_encoding(sample: bytes) -> str:
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return "cp1252"
    return "utf-8"


def portable_path(path: Path, project_root: Path = PROJECT_ROOT) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _year_from_path(path: Path) -> int:
    match = re.search(r"(20\d{2})", path.name)
    if match is None:
        raise DataImportError(
            path.name,
            "o ano não pôde ser identificado pelo nome do arquivo",
            "renomeie o arquivo incluindo o ano, por exemplo receitas-2025.zip",
        )
    return int(match.group(1))


def filter_tce_archive(
    archive_path: Path,
    output_path: Path,
    municipality: str,
    *,
    source_url: str | None = None,
) -> SourceMetadata:
    temporary = output_path.with_suffix(output_path.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        try:
            with ZipFile(archive_path) as archive:
                members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
                if len(members) != 1:
                    raise DataImportError(
                        archive_path.name,
                        "o ZIP precisa conter exatamente um arquivo CSV",
                        "confira o arquivo oficial baixado do TCE-SP",
                    )
                member = members[0]
                with archive.open(member) as raw:
                    encoding = detect_encoding(raw.read(64 * 1024))

                output_path.parent.mkdir(parents=True, exist_ok=True)
                wrote_header = False
                row_count = 0
                with archive.open(member) as raw:
                    chunks = pd.read_csv(
                        raw,
                        sep=";",
                        encoding=encoding,
                        dtype=str,
                        keep_default_na=False,
                        chunksize=100_000,
                    )
                    for chunk in chunks:
                        if "ds_municipio" not in chunk.columns:
                            raise DataImportError(
                                archive_path.name,
                                "a coluna obrigatória ds_municipio não foi encontrada",
                                "verifique se o conjunto baixado é o de receitas municipais",
                            )
                        selected = chunk.loc[chunk["ds_municipio"] == municipality]
                        if selected.empty:
                            continue
                        selected.to_csv(
                            temporary,
                            sep=";",
                            encoding="utf-8",
                            index=False,
                            mode="a" if wrote_header else "w",
                            header=not wrote_header,
                        )
                        wrote_header = True
                        row_count += len(selected)
        except BadZipFile as error:
            raise DataImportError(
                archive_path.name,
                "o arquivo baixado não é um ZIP válido",
                "baixe novamente o conjunto oficial",
            ) from error

        if row_count == 0:
            raise DataImportError(
                archive_path.name,
                f"nenhuma linha foi encontrada para {municipality}",
                "confira o nome do município e o conteúdo do conjunto",
            )
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)

    year = _year_from_path(archive_path)
    return SourceMetadata(
        source_url=source_url or TCE_SOURCES.get(year, ""),
        source_year=year,
        retrieved_at=datetime.fromtimestamp(
            archive_path.stat().st_mtime, timezone.utc
        ).isoformat(),
        source_checksum_sha256=sha256_file(archive_path),
        filtered_checksum_sha256=sha256_file(output_path),
        source_encoding=encoding,
        row_count=row_count,
        raw_file=portable_path(output_path),
    )


def write_metadata(metadata: SourceMetadata, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".part")
    temporary.write_text(
        json.dumps(asdict(metadata), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "receitas-martinopolis/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as target:
            shutil.copyfileobj(response, target, length=1024 * 1024)
    except (OSError, urllib.error.URLError) as error:
        temporary.unlink(missing_ok=True)
        raise DataImportError(
            destination.name,
            f"falha ao baixar o conjunto oficial: {error}",
            "verifique a conexão e tente novamente",
        ) from error
    temporary.replace(destination)


def download_all(
    years: Sequence[int],
    *,
    municipality: str,
    cache_dir: Path = CACHE_DIR,
    raw_dir: Path = RAW_TCE_DIR,
    metadata_dir: Path = METADATA_DIR,
) -> tuple[SourceMetadata, ...]:
    results: list[SourceMetadata] = []
    for year in years:
        if year not in TCE_SOURCES:
            raise ValueError(f"Unsupported TCE year: {year}")
        archive_path = cache_dir / f"receitas-{year}.zip"
        if not archive_path.exists():
            _download(TCE_SOURCES[year], archive_path)
        raw_path = raw_dir / f"martinopolis-receitas-{year}.csv"
        metadata = filter_tce_archive(
            archive_path,
            raw_path,
            municipality,
            source_url=TCE_SOURCES[year],
        )
        write_metadata(metadata, metadata_dir / f"receitas-{year}.json")
        results.append(metadata)
    return tuple(results)
