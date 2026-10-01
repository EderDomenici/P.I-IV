import pandas as pd
import pytest

from receitas.categories import apply_categories, classify_revenue


@pytest.mark.parametrize(
    ("code", "description", "expected"),
    [
        ("11125001", "IPTU - Principal", "IPTU"),
        ("11145111", "ISS - Principal", "ISS"),
        ("11130311", "IRRF - Trabalho", "IRRF"),
        ("17115111", "Cota-Parte do FPM", "FPM"),
        ("17215001", "Cota-Parte do ICMS", "ICMS"),
        ("17215101", "Cota-Parte do IPVA", "IPVA"),
        ("17515001", "Transferências do FUNDEB", "FUNDEB"),
        ("17135001", "Transferências de Recursos do SUS", "Saúde"),
        ("11180111", "Imposto sobre a Propriedade Predial e Territorial Urbana", "IPTU"),
        ("11180231", "Imposto sobre Serviços de Qualquer Natureza", "ISS"),
        ("17280111", "Cota-Parte do ICMS - Principal", "ICMS"),
        ("17280121", "Cota-Parte do IPVA - Principal", "IPVA"),
        ("99999999", "Tarifa de água residencial", "Água"),
        ("99999998", "Serviço de esgoto sanitário", "Esgoto"),
        ("99999997", "Receita não mapeada", "Não classificada"),
    ],
)
def test_classify_revenue(code: str, description: str, expected: str) -> None:
    assert classify_revenue(code, description) == expected


def test_apply_categories_preserves_original_description() -> None:
    frame = pd.DataFrame(
        {"revenue_code": ["17115111"], "revenue_description": ["Cota-Parte do FPM"]}
    )

    result = apply_categories(frame)

    assert result.loc[0, "category"] == "FPM"
    assert result.loc[0, "revenue_description"] == "Cota-Parte do FPM"
