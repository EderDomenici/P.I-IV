# Guia de implementação — análise da receita municipal de Martinópolis

## Contexto e intenção

Este é um projeto **acadêmico**, sem finalidade comercial. A proposta é transformar dados públicos de receita do Portal da Transparência de Martinópolis em um dashboard que ajude vereadores a compreender a arrecadação, comparar períodos e consultar uma estimativa para os meses seguintes. A ferramenta apoia a análise humana; não determina irregularidades nem substitui trabalho contábil.

## Instrução para o agente implementador

Implemente um MVP local, simples e reproduzível. Antes de codificar, inspecione os arquivos e a estrutura do repositório. Use os dados realmente disponíveis; não invente registros, totais, campos ou resultados de modelos. Se não houver dados reais no projeto, deixe o importador preparado e documente os arquivos necessários. Dados sintéticos, se úteis para testar a interface, devem ser claramente marcados e nunca exibidos como resultados do município.

Prefira Python, Pandas, Plotly e Streamlit. Use scikit-learn somente quando houver dados mensais suficientes para treinar e avaliar uma previsão. SQLite é opcional: arquivos locais tratados (CSV ou Parquet) bastam para o MVP. Evite autenticação, API própria, frontend separado e infraestrutura de produção.

## Escopo do MVP

1. Importar arquivos de receita exportados do Portal da Transparência, preferencialmente CSV ou XLS/XLSX. A atualização pode ser manual.
2. Consolidar os exercícios completos de **2021 a 2025** e o período disponível de **2026**, identificado como parcial. Preparar o fluxo para incorporar arquivos mensais de janeiro de 2021 em diante.
3. Tratar códigos, descrições, períodos, fontes, aplicações e valores de receita, preservando o arquivo bruto e a origem de cada registro.
4. Exibir um dashboard com arrecadação, previsão orçamentária quando disponível, percentual realizado, composição por receita, evolução mensal e comparação entre exercícios.
5. Produzir pelo menos uma previsão de arrecadação para receita com série mensal adequada, mostrar o erro medido em dados históricos e distinguir valores observados dos estimados.
6. Adicionar indicação experimental de comportamento atípico somente se a qualidade dos dados permitir e houver tempo. Apresentá-la como ponto para investigação, nunca como irregularidade.

Ficam fora do escopo despesas, contratos, licitações, folha de pagamento, auditoria automática, coleta automática obrigatória e publicação comercial.

## Regras essenciais dos dados

- Examine a estrutura real dos relatórios antes de definir o esquema final. Campos candidatos: código, especificação, código de aplicação, fonte STN, fonte de recurso, previsão inicial, previsão atualizada, arrecadação do período e arrecadação acumulada.
- Registre, para cada importação: nome do arquivo, origem, ano, mês ou intervalo coberto e data da importação. Não misture arquivos anuais e mensais na mesma soma.
- **Preserve a hierarquia contábil.** Linhas agregadoras e linhas detalhadas representam níveis da mesma receita. Não some todas as linhas indiscriminadamente: isso duplica valores. Defina e documente qual nível entra em cada indicador; confronte os totais calculados com os totais publicados.
- Confirme se cada coluna representa valor **do período** ou **acumulado**. Se for acumulado, calcule os meses por diferença apenas depois de verificar a consistência da série; preserve ajustes, estornos e valores negativos legítimos.
- Padronize formatos de data e moeda, inclusive separadores brasileiros. Trate duplicatas de exportação e códigos que mudaram de descrição ou classificação entre anos. Não force equivalência de códigos ambíguos: registre-os para revisão.
- Categorias iniciais para verificar nos dados: FPM, ICMS, FUNDEB, transferências da Saúde, ISS, IPVA, IPTU, Água, IRRF e Esgoto. A lista final depende da relevância e da consistência observadas. “Outras receitas” deve ser o restante definido após classificar as categorias principais, preservando o detalhamento original.
- Compare períodos equivalentes: por exemplo, janeiro a agosto de 2026 com janeiro a agosto de anos anteriores. Identifique na interface que 2026 é parcial.

## Interface mínima

Uma aplicação Streamlit com:

- filtros de ano, intervalo e categoria de receita; filtros de fonte e aplicação somente se os dados estiverem consistentes;
- cartões com receita arrecadada, previsão atualizada e percentual realizado, quando disponíveis;
- gráfico de evolução mensal e gráfico de composição das principais receitas;
- comparação de períodos equivalentes entre anos;
- visualização da previsão com observados e estimados separados, horizonte e medida de erro;
- indicação clara do período coberto, da fonte dos dados e das limitações da análise.

A interface deve funcionar mesmo quando não houver série apta à previsão: explique a insuficiência de dados em vez de fabricar uma previsão.

## Previsão: abordagem pragmática

1. Escolha uma receita recorrente com meses suficientes e classificação estável. Documente a escolha.
2. Ordene a série por data e reserve os meses mais recentes para teste. Não embaralhe dados temporais nem use valores futuros como entrada do treino.
3. Compare uma referência simples, como repetir o valor do mesmo mês do ano anterior quando possível, com pelo menos um modelo apropriado aos dados disponíveis. Se o requisito acadêmico exigir aprendizagem de máquina, inclua um modelo efetivamente treinado e avaliado, como uma regressão com defasagens e mês do ano. Escolha após observar os dados, sem fixar um algoritmo por conveniência.
4. Meça o erro em períodos não usados no treino (por exemplo, MAE) e apresente esse resultado junto à previsão. Se a série for curta, instável ou tiver mudanças de classificação, registre a limitação e restrinja a conclusão.
5. A previsão representa uma **estimativa baseada no histórico**, não garantia de arrecadação.

## Ordem de execução sugerida

1. **Diagnóstico:** listar arquivos existentes, entender formatos, períodos, totais e hierarquia; registrar lacunas.
2. **Importação:** criar um módulo para ler e padronizar os arquivos, com configuração explícita para diferenças entre formatos.
3. **Validação:** conferir períodos, duplicatas, tipos, nível hierárquico e conciliação dos totais com a fonte.
4. **Análise:** gerar agregações mensais e anuais e categorias principais sem dupla contagem.
5. **Dashboard:** implementar filtros, indicadores e gráficos usando apenas resultados validados.
6. **Previsão:** treinar, testar e apresentar a aplicação de ML se houver série elegível.
7. **Revisão:** executar com dados reais disponíveis, documentar decisões, limitações e instruções de reprodução.

## Entregáveis esperados

- Código organizado em módulos simples para importação/tratamento, análise, previsão e interface.
- `requirements.txt` (ou equivalente) com dependências necessárias.
- `README.md` com instalação, comando de execução, local e formato esperado dos dados, fonte dos arquivos, período coberto e limitações.
- Breve registro das regras de classificação e dos resultados da validação, incluindo qualquer divergência entre os totais calculados e a fonte.
- Testes pequenos para as regras que podem produzir erro material: conversão de valores, prevenção de dupla contagem, tratamento de períodos e cálculo de métricas da previsão.

## Critérios de conclusão

- O dashboard inicia localmente e funciona com os arquivos reais fornecidos.
- O total exibido pode ser rastreado até a fonte e não contém dupla contagem de níveis hierárquicos.
- 2026 aparece como período parcial e as comparações usam a mesma janela de meses.
- A previsão, quando apresentada, mostra horizonte, dados observados, método e erro histórico; quando inviável, a interface informa o motivo.
- Outra pessoa consegue reproduzir a preparação dos dados e a execução seguindo o README.

## Conduta em caso de lacunas

Se faltar arquivo mensal, dicionário de códigos ou informação para distinguir níveis hierárquicos, conclua as partes possíveis, registre exatamente o impedimento e indique o dado necessário para continuar. Não preencha a lacuna com uma hipótese silenciosa.
