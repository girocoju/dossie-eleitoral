# ADR-009 — Particionamento por inteiro e carga da tabela inteira

**Status:** Aceita · **Data:** 2026-08-27 · **Substitui parte de:** [ADR-002](ADR-002-import-mode.md)

## Contexto

O desenho original das tabelas `raw_*` particionava por DIA sobre uma coluna
`data_particao` igual a 1o de janeiro do ano de referencia. Isso permitia usar o
decorador `tabela$YYYYMMDD` numa carga `WRITE_TRUNCATE` e **substituir apenas a
particao daquele ano**, sem nenhum SQL fora do dbt — exatamente o criterio de
F-01 ("reexecutar nao duplica linhas").

O projeto roda no **BigQuery sandbox** (sem cartao, custo zero garantido — decisao
tomada com o dono do projeto). O sandbox impoe expiracao de 60 dias por particao,
e o prazo conta a partir da **data da particao**, nao da data da carga.

Conferido em 27/08/2026: a carga reportou 20.765 linhas gravadas e a tabela
ficou com **0 linhas**. A particao `2026-01-01` nasceu com 239 dias de idade e foi
descartada imediatamente. Com o historico seria pior: uma particao de 1998
expiraria instantaneamente.

## Decisao

1. `raw_*` passa a ser particionada por **intervalo de inteiros** sobre
   `ano_eleicao` (`ano` nos indicadores), faixa 1990–2040, intervalo 1.
   Particao por inteiro nao tem expiracao por data.
2. A coluna `data_particao` deixa de existir.
3. Como o BigQuery **nao aceita decorador de particao em carga para tabelas
   particionadas por inteiro**, a idempotencia passa a vir de outro lugar: a carga
   **substitui a tabela inteira** a partir de todos os NDJSON daquele dataset
   presentes em `data/staging`. O primeiro arquivo entra com `WRITE_TRUNCATE`, os
   demais com `WRITE_APPEND`.

## Motivo

- Mantem a Constituicao secao 5 (custo proximo de zero) sem cartao de credito.
- Mantem a Constituicao secao 4 e F-01: reexecutar continua nao duplicando, porque a
  tabela final e' funcao exclusiva dos arquivos em disco.
- Mantem SPEC secao 9 (nenhum SQL fora do dbt): a alternativa seria `MERGE`/`DELETE`,
  isto e', SQL de manutencao fora do dbt.
- O volume torna a perda de granularidade irrelevante: sao ~20 mil linhas por ano
  de eleicao, oito anos no total.

## Consequencia

- **Carregar um ano exige ter os NDJSON dos outros anos em disco.** Se so' 2026
  estiver em `data/staging`, a tabela passa a conter so' 2026. O loader registra em
  log exatamente quais anos entraram, e avisa quando carrega mais de um.
  No GitHub Actions isso e' garantido pelo cache de `data/`.
- **As tabelas ainda expiram em 60 dias** no sandbox (expiracao de tabela, nao de
  particao). O pipeline precisa rodar ao menos uma vez a cada dois meses; o
  agendamento semanal ja' cobre isso com folga.
- Se um dia o faturamento for ativado, nada aqui precisa mudar — a decisao continua
  correta, apenas deixa de ser obrigatoria.
