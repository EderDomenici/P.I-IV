# Data validation

## Source inventory
- `martinopolis-receitas-2021.csv`: 948 rows
- `martinopolis-receitas-2022.csv`: 1112 rows
- `martinopolis-receitas-2023.csv`: 1256 rows
- `martinopolis-receitas-2024.csv`: 1109 rows
- `martinopolis-receitas-2025.csv`: 1245 rows

## Temporal coverage
- 2021: months 1–12, 948 rows
- 2022: months 1–12, 1112 rows
- 2023: months 1–12, 1256 rows
- 2024: months 1–12, 1109 rows
- 2025: months 1–12, 1245 rows

## Hierarchy decision
All rows used by indicators are detail rows; aggregate ancestors are excluded.

## Duplicate checks
Duplicate source rows: 0.

## Category coverage
- FPM: 174 rows
- FUNDEB: 63 rows
- ICMS: 120 rows
- IPTU: 252 rows
- IPVA: 120 rows
- IRRF: 93 rows
- ISS: 245 rows
- Não classificada: 3940 rows
- Saúde: 663 rows

## Budget availability
The TCE source does not provide updated budget forecasts.

## Forecast eligibility
- FPM: eligible (60 complete months)
- FUNDEB: eligible (60 complete months)
- ICMS: eligible (60 complete months)
- IPTU: eligible (60 complete months)
- IPVA: eligible (60 complete months)
- IRRF: eligible (60 complete months)
- ISS: eligible (60 complete months)
- Não classificada: eligible (60 complete months)
- Saúde: eligible (60 complete months)

## Blocking issues
- None

## Warnings
- `BUDGET_UNAVAILABLE`: The source does not provide an updated budget forecast.
- `UNCLASSIFIED_REVENUE`: Some revenue codes do not have an analytical category.
