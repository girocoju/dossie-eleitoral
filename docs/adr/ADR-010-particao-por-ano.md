# ADR-010 — Volta da particao por ano com substituicao cirurgica

**Status:** Aceita · **Data:** 2026-08-27 · **Substitui:** [ADR-009](ADR-009-particionamento-sandbox.md)

## Contexto

O [ADR-009](ADR-009-particionamento-sandbox.md) trocou a particao por DIA (com
decorador `tabela$YYYY0101`) por particao de inteiro e carga da tabela inteira,
porque o BigQuery sandbox expirava particoes datadas no passado. O faturamento foi
ativado em 27/08/2026 e essa restricao deixou de existir.

O gatilho para revisar nao foi estetico. O snapshot diario das candidaturas exige
que o pipeline rode **todo dia ate' 04/10/2026**, num runner limpo do GitHub
Actions. Com a carga de tabela inteira, esse runner teria em disco apenas os NDJSON
de 2026 — e a tabela `raw_tse.candidatos` passaria de 180.718 para 20.765 linhas,
levando `fct_mandato` de 11.777 para perto de zero. **Em silencio**, porque cada
carga isolada continuaria "correta".

A propria secao de consequencias do ADR-009 previa o risco ("carregar um ano exige
ter os NDJSON dos outros anos em disco"). O que mudou e' que ele deixou de ser
teorico.

## Decisao

Voltar a' particao por DIA sobre `data_particao` (1o de janeiro do ano de
referencia) nas tabelas `raw_tse.*`, e carregar com o decorador
`tabela$YYYY0101` em `WRITE_TRUNCATE`. Recarregar 2026 nao toca em 1998–2022.

A carga de tabela inteira (`load_ndjson`, multi-arquivo) permanece — e' o que as
tabelas de indicadores usam, porque elas sao pequenas e sempre vem completas da
API.

## Motivo

- E' literalmente o que F-01 pede: "reexecutar nao duplica linhas (carga substitui
  particao do ano)".
- Torna o pipeline diario seguro por construcao, e nao por disciplina operacional.
- Continua sem nenhum SQL fora do dbt (SPEC 9): decorador de particao e' opcao de
  job de carga, nao DML.

## Consequencia

- Volta a coluna `data_particao`, redundante com `ano_eleicao` mas necessaria como
  chave de particionamento por data.
- Depende de faturamento ativo. Se o projeto voltar ao sandbox, as particoes
  datadas no passado expiram de novo e o ADR-009 volta a valer — junto com a
  obrigacao de carregar todos os anos a cada execucao.
