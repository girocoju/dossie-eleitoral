# ADR-002 — Import mode sobre tabelas agregadas

**Status:** Aceita · **Data:** 2026-08-27 · **Origem:** SPEC secao 10

## Contexto
DirectQuery faria o BigQuery cobrar bytes processados a cada interacao do usuario
com o relatorio publicado. A Constituicao secao 5 exige custo proximo de zero,
dentro do free tier (10 GB de armazenamento, 1 TB de query por mes).

## Decisao
Import mode. O Power BI le' apenas as tabelas de `marts`, que ja' chegam agregadas.

## Motivo
- Um relatorio publico com DirectQuery tem custo proporcional ao numero de
  visitantes — exatamente o que nao se quer num portfolio.
- Os marts sao pequenos: `fct_candidatura` tem ~41 mil linhas para 2026 e
  `fct_indicador_uf_ano` fica na casa dos milhares.

## Consequencia
- O relatorio publicado mostra o dado do ultimo refresh, nao o dado ao vivo. O
  rodape de cada pagina exibe `_extracted_at` para que isso fique explicito.
- O detalhe por municipio/zona (S4) nunca pode ir para o modelo sem agregacao
  previa no dbt.
