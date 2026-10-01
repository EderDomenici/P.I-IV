from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from receitas.acquisition import (
    portable_path,
    detect_encoding,
    filter_tce_archive,
    sha256_file,
    write_metadata,
)
from receitas.errors import DataImportError


TCE_COLUMNS = [
    "id_rec_arrec_detalhe",
    "ano_exercicio",
    "ds_municipio",
    "ds_orgao",
    "mes_referencia",
    "mes_ref_extenso",
    "ds_poder",
    "ds_fonte_recurso",
    "ds_cd_aplicacao_fixo",
    "ds_cd_aplicacao_variavel",
    "ds_categoria",
    "ds_subcategoria",
    "ds_fonte",
    "ds_d1",
    "ds_dd2",
    "ds_d3",
    "ds_tipo",
    "vl_arrecadacao",
]


def _row(identifier: str, municipality: str, value: str) -> str:
    values = [
        identifier,
        "2025",
        municipality,
        f"PREFEITURA MUNICIPAL DE {municipality.upper()}",
        "1",
        "Janeiro",
        "EXECUTIVO",
        "01 - TESOURO",
        "110 - GERAL",
        "00 - NÃO INFORMADO",
        "10000000 - Receitas Correntes",
        "11000000 - Impostos",
        "11100000 - Impostos",
        "11120000 - Patrimônio",
        "11125000 - IPTU",
        "11125000 - IPTU",
        "11125001 - IPTU - Principal",
        value,
    ]
    return ";".join(values)


def build_archive(tmp_path: Path, encoding: str = "cp1252") -> Path:
    content = "\n".join(
        [
            ";".join(TCE_COLUMNS),
            _row("1", "Martinópolis", "767,79"),
            _row("2", "Adamantina", "50,00"),
            _row("3", "Martinópolis", "-10,00"),
        ]
    ) + "\n"
    archive = tmp_path / "receitas-2025.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        zipped.writestr("receitas-2025.csv", content.encode(encoding))
    return archive


def test_detect_encoding_prefers_utf8_and_accepts_cp1252() -> None:
    assert detect_encoding("Martinópolis".encode("utf-8")) == "utf-8"
    assert detect_encoding("Martinópolis".encode("cp1252")) == "cp1252"


def test_filter_tce_archive_keeps_only_martinopolis_and_original_columns(tmp_path: Path) -> None:
    output = tmp_path / "martinopolis-2025.csv"

    metadata = filter_tce_archive(build_archive(tmp_path), output, "Martinópolis")
    frame = pd.read_csv(output, sep=";", encoding="utf-8", dtype=str)

    assert frame["ds_municipio"].tolist() == ["Martinópolis", "Martinópolis"]
    assert frame.columns.tolist() == TCE_COLUMNS
    assert metadata.row_count == 2
    assert metadata.source_encoding == "cp1252"
    assert metadata.source_year == 2025


def test_filter_tce_archive_uses_bounded_chunks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[int | None] = []
    original = pd.read_csv

    def tracked_read_csv(*args: object, **kwargs: object) -> object:
        calls.append(kwargs.get("chunksize"))
        return original(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", tracked_read_csv)

    filter_tce_archive(build_archive(tmp_path), tmp_path / "out.csv", "Martinópolis")

    assert calls == [100_000]


def test_filter_rejects_missing_municipality_column(tmp_path: Path) -> None:
    archive = tmp_path / "receitas-2025.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("receitas-2025.csv", b"ano_exercicio;valor\n2025;10\n")

    with pytest.raises(DataImportError, match="ds_municipio"):
        filter_tce_archive(archive, tmp_path / "out.csv", "Martinópolis")


def test_filter_failure_preserves_previous_valid_extract(tmp_path: Path) -> None:
    archive = tmp_path / "receitas-2025.zip"
    content = ";".join(TCE_COLUMNS) + "\n" + _row("1", "Adamantina", "50,00") + "\n"
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        zipped.writestr("receitas-2025.csv", content.encode("utf-8"))
    output = tmp_path / "martinopolis-2025.csv"
    output.write_text("previous-valid-extract\n", encoding="utf-8")

    with pytest.raises(DataImportError, match="nenhuma linha"):
        filter_tce_archive(archive, output, "Martinópolis")

    assert output.read_text(encoding="utf-8") == "previous-valid-extract\n"


def test_sha256_and_metadata_output_are_stable(tmp_path: Path) -> None:
    archive = build_archive(tmp_path, encoding="utf-8")
    output = tmp_path / "out.csv"
    metadata = filter_tce_archive(archive, output, "Martinópolis")
    metadata_path = tmp_path / "metadata.json"

    write_metadata(metadata, metadata_path)

    assert sha256_file(archive) == hashlib.sha256(archive.read_bytes()).hexdigest()
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["source_year"] == 2025
    assert payload["filtered_checksum_sha256"] == sha256_file(output)


def test_portable_path_is_relative_inside_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    raw = project / "data" / "raw" / "file.csv"

    assert portable_path(raw, project) == "data/raw/file.csv"
    assert portable_path(tmp_path / "external.csv", project) == str(tmp_path / "external.csv")


def test_cached_archive_keeps_original_retrieval_timestamp(tmp_path: Path) -> None:
    archive = build_archive(tmp_path)

    first = filter_tce_archive(archive, tmp_path / "first.csv", "Martinópolis")
    second = filter_tce_archive(archive, tmp_path / "second.csv", "Martinópolis")

    assert first.retrieved_at == second.retrieved_at
