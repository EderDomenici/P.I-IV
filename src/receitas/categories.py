from __future__ import annotations

import unicodedata

import pandas as pd


CODE_RULES: tuple[tuple[str, str], ...] = (
    ("111801", "IPTU"),
    ("1118023", "ISS"),
    ("1728011", "ICMS"),
    ("1728012", "IPVA"),
    ("111250", "IPTU"),
    ("111451", "ISS"),
    ("111303", "IRRF"),
    ("171151", "FPM"),
    ("172150", "ICMS"),
    ("172151", "IPVA"),
    ("175150", "FUNDEB"),
    ("171350", "Saúde"),
)


def _plain_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character)).lower()


def classify_revenue(code: str, description: str) -> str:
    normalized_code = "".join(character for character in str(code) if character.isdigit())
    for prefix, category in CODE_RULES:
        if normalized_code.startswith(prefix):
            return category

    text = _plain_text(str(description))
    if "fundeb" in text:
        return "FUNDEB"
    if "fundo de participacao dos municipios" in text or "cota-parte do fpm" in text:
        return "FPM"
    if "sistema unico de saude" in text or "recursos do sus" in text:
        return "Saúde"
    if "esgoto" in text:
        return "Esgoto"
    if "agua" in text:
        return "Água"
    return "Não classificada"


def apply_categories(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["category"] = [
        classify_revenue(code, description)
        for code, description in zip(
            result["revenue_code"], result["revenue_description"], strict=True
        )
    ]
    return result
