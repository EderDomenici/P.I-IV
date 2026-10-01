# Dashboard de Receitas de Martinópolis

Projeto acadêmico local para analisar receitas municipais de Martinópolis/SP.
Ele utiliza dados públicos do Tribunal de Contas do Estado de São Paulo
(TCE-SP), apresenta comparações entre exercícios e calcula uma previsão
estatística simples avaliada em dados históricos.

O dashboard **não identifica irregularidades**, não substitui análise contábil e
não representa garantia de arrecadação futura.

## O que está disponível

- dados reais e completos de janeiro de 2021 a dezembro de 2025;
- 5.670 registros municipais rastreáveis até os recortes oficiais;
- indicadores de arrecadação e composição por categoria;
- evolução mensal e comparação de períodos equivalentes;
- previsão sazonal ingênua comparada com média móvel de 12 meses;
- avaliação cronológica com os 12 meses finais e apresentação do MAE;
- importação opcional de arquivo parcial de 2026 em CSV, XLS ou XLSX.

O ano de 2026 não aparece enquanto nenhum arquivo real for importado.

## Requisitos

- Python 3.11 ou superior;
- acesso à internet somente para baixar os conjuntos oficiais;
- aproximadamente 3 GB livres durante o download e a extração em fluxo.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install -e '.[dev]'
```

## Obtenção dos dados oficiais

Os arquivos anuais são publicados na página de
[Conjuntos de Dados do TCE-SP](https://transparencia.tce.sp.gov.br/conjunto-de-dados).

Para baixar 2021–2025 e manter somente Martinópolis:

```bash
python scripts/download_tce_data.py
```

O script:

1. baixa cada ZIP para `data/cache/`;
2. lê o CSV estadual em blocos de 100 mil linhas;
3. seleciona exatamente `Martinópolis`;
4. grava o recorte original em `data/raw/tce/`;
5. registra URLs, datas, codificações, quantidades e checksums em
   `data/metadata/`.

Os ZIPs completos são cache local ignorado pelo Git. Os recortes municipais e
seus metadados são os insumos auditáveis do projeto.

## Preparação

```bash
python scripts/prepare_data.py
```

Saídas:

- `data/processed/revenues.parquet`;
- `data/processed/validation-report.json`;
- `docs/data-validation.md`.

O Parquet somente é substituído quando não existem erros bloqueantes. O relatório
é escrito mesmo quando a validação bloqueia a publicação.

## Importação opcional de 2026

O significado da coluna monetária precisa ser explícito.

Valores de cada mês:

```bash
python scripts/prepare_data.py \
  --manual data/raw/manual/receitas-2026.xlsx \
  --value-semantics period
```

Valores acumulados:

```bash
python scripts/prepare_data.py \
  --manual data/raw/manual/receitas-2026.xlsx \
  --value-semantics cumulative
```

Para arquivos acumulados, o sistema calcula diferenças mensais somente quando a
série é consecutiva. Ajustes negativos são preservados. Uma lacuna mensal bloqueia
a conversão.

Colunas reconhecidas incluem variações de:

- `ano`, `mes`, `codigo` e `especificacao`;
- `fonte` e `codigo_aplicacao`;
- `previsao_inicial` e `previsao_atualizada`;
- `arrecadado_periodo` ou `arrecadado_acumulado`;
- `tipo_linha`, com valores como `detalhe`, `analitica`, `agregado` ou
  `sintetica`.

Uma planilha sem identificação segura de período, valor ou hierarquia é rejeitada
com uma mensagem indicando a correção necessária.

## Execução do dashboard

```bash
streamlit run app.py
```

Acesse `http://localhost:8501`.

O dashboard contém:

- **Visão geral:** arrecadação e composição;
- **Evolução mensal:** série filtrada por exercício e categoria;
- **Comparação entre anos:** mesma janela de meses para todos os exercícios;
- **Previsão e qualidade:** observados, estimados, método, MAE, horizonte e
  ocorrências da validação.

A previsão orçamentária aparece como indisponível porque o conjunto de receitas
do TCE-SP não fornece esse campo.

## Previsão estatística

Cada categoria candidata precisa ter pelo menos 36 meses completos, consecutivos
e sem valores ausentes. Os últimos 12 meses são separados para avaliação.

São comparados:

1. o valor observado no mesmo mês do ano anterior;
2. a média recursiva dos 12 meses anteriores.

O método com menor erro absoluto médio (MAE) é utilizado. Em empate, vence o
método sazonal ingênuo por ser mais simples de explicar. Dados futuros nunca são
usados no treinamento ou na avaliação dos meses anteriores.

## Testes

```bash
python -m pytest -v
```

Os testes cobrem moeda brasileira, períodos, esquemas TCE de 2021 e 2022–2025,
importação manual, acumulados, duplicatas, hierarquia, categorias, comparação de
períodos, previsão, MAE, pipeline atômica e auxiliares da interface.

## Estrutura dos dados

- `data/raw/tce/`: recortes oficiais por exercício;
- `data/raw/manual/`: arquivo opcional fornecido pelo usuário;
- `data/metadata/`: proveniência e checksums;
- `data/processed/`: artefatos regeneráveis;
- `docs/data-validation.md`: resultado medido da validação atual.

## Limitações

- não há dados reais de 2026 no projeto;
- o TCE-SP não fornece previsão orçamentária neste conjunto;
- receitas não mapeadas permanecem como `Não classificada` e preservam código e
  descrição originais;
- não há detecção automática de anomalias ou irregularidades;
- não foi fornecido um total de controle externo separado para conciliação; os
  totais são rastreáveis às linhas oficiais e internamente consistentes;
- a atualização é manual e local.
