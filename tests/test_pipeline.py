from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from receitas.errors import ValidationBlockedError
from receitas.pipeline import prepare_dataset


def write_tce_file(path: Path, year: int, *, duplicate: bool = False) -> Path:
    identifiers = [f"{year}-1", f"{year}-1" if duplicate else f"{year}-2"]
    frame = pd.DataFrame(
        {
            "id_rec_arrec_detalhe": identifiers,
            "ano_exercicio": [str(year), str(year)],
            "ds_municipio": ["Martinópolis", "Martinópolis"],
            "ds_orgao": ["PREFEITURA", "PREFEITURA"],
            "mes_referencia": ["1", "2"],
            "mes_ref_extenso": ["Janeiro", "Fevereiro"],
            "ds_poder": ["EXECUTIVO", "EXECUTIVO"],
            "ds_fonte_recurso": ["01 - TESOURO", "01 - TESOURO"],
            "ds_cd_aplicacao_fixo": ["110 - GERAL", "110 - GERAL"],
            "ds_cd_aplicacao_variavel": ["00 - NÃO INFORMADO", "00 - NÃO INFORMADO"],
            "ds_categoria": ["10000000 - Receitas Correntes"] * 2,
            "ds_subcategoria": ["17000000 - Transferências"] * 2,
            "ds_fonte": ["17100000 - União"] * 2,
            "ds_d1": ["17110000 - Participações"] * 2,
            "ds_dd2": ["17115100 - FPM"] * 2,
            "ds_d3": ["17115100 - FPM"] * 2,
            "ds_tipo": ["17115111 - Cota-Parte do FPM"] * 2,
            "vl_arrecadacao": ["100,00", "120,00"],
        }
    )
    frame.to_csv(path, sep=";", index=False)
    return path


def test_prepare_dataset_writes_traceable_artifacts(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    paths = [write_tce_file(raw_dir / f"martinopolis-receitas-{year}.csv", year) for year in range(2021, 2026)]

    result = prepare_dataset(paths, tmp_path / "processed", tmp_path / "data-validation.md")
    frame = pd.read_parquet(result.parquet_path)
    report = json.loads(result.validation_json_path.read_text(encoding="utf-8"))

    assert set(frame["fiscal_year"]) == {2021, 2022, 2023, 2024, 2025}
    assert frame[["source_file", "source_row"]].notna().all().all()
    assert report["blocked"] is False
    assert result.validation_markdown_path.exists()
    assert "## Hierarchy decision" in result.validation_markdown_path.read_text(encoding="utf-8")


def test_blocked_dataset_does_not_replace_valid_parquet(tmp_path: Path) -> None:
    output_dir = tmp_path / "processed"
    output_dir.mkdir()
    existing = output_dir / "revenues.parquet"
    existing.write_bytes(b"previous-valid-artifact")
    raw = write_tce_file(tmp_path / "martinopolis-receitas-2025.csv", 2025, duplicate=True)

    with pytest.raises(ValidationBlockedError):
        prepare_dataset([raw], output_dir, tmp_path / "validation.md")

    assert existing.read_bytes() == b"previous-valid-artifact"
    payload = json.loads((output_dir / "validation-report.json").read_text(encoding="utf-8"))
    assert payload["blocked"] is True
