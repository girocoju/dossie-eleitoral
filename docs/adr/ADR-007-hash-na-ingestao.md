# ADR-007 — O hash e' calculado na ingestao; o CPF nunca chega ao warehouse

**Status:** Aceita · **Data:** 2026-08-27

## Contexto
A Constituicao secao 4 diz que `raw_*` e' "copia fiel da fonte". O arquivo do TSE
traz `NR_CPF_CANDIDATO`, `NR_TITULO_ELEITORAL_CANDIDATO` e `DS_EMAIL` em claro.
Copia fiel e Constituicao secao 7 ("nao expoe CPF nem endereco") colidem aqui.

## Decisao
A colisao e' resolvida a favor da privacidade, e de forma declarada:
`ingest/layouts/tse_base.yml` tem um bloco `privacidade` com

- `descartar`: colunas que somem antes do NDJSON — nem em `_extras` sobram;
- `hash`: colunas substituidas pelo HMAC ([ADR-006](ADR-006-hmac-no-cpf.md)).

`raw_tse` e' copia fiel **de tudo o mais**. O CPF em claro nao existe em disco
depois da leitura do CSV, nem no BigQuery, nem no Power BI.

## Motivo
- Minimizacao de dado: o que nao e' coletado nao vaza.
- Colocar a regra no YAML, e nao no `.py`, mantem auditavel **o que exatamente**
  e' descartado — a lista e' um dado, nao uma linha perdida no meio do codigo.
- Um teste dbt (`assert_cpf_nunca_persistido`) e um teste Python guardam a regra.

## Consequencia
- Recalcular hashes com outro salt exige rebaixar os pacotes do TSE. O cache de
  download torna isso barato.
- `raw_tse` deixa de ser byte-a-byte identico a' fonte. A excecao esta' declarada
  no layout, neste ADR e em `docs/METODOLOGIA.md`.
