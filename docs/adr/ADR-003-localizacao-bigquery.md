# ADR-003 — Datasets do BigQuery na multi-regiao `US`

**Status:** Aceita (era Pendente no SPEC) · **Data:** 2026-08-27

## Contexto
`southamerica-east1` (Sao Paulo) reduz latencia para quem esta' no Brasil.
`US` e' onde vivem os datasets publicos da Base dos Dados. Um join entre datasets
de localizacoes diferentes e' impossivel no BigQuery — a localizacao precisa ser
escolhida antes da primeira tabela existir.

## Decisao
Todos os datasets (`raw_tse`, `raw_ibge`, `raw_ipea`, `stg`, `marts`) em `US`.

## Motivo
- Mesmo com [ADR-004](ADR-004-fonte-do-historico.md) decidindo nao depender da
  Base dos Dados para a carga, ela continua sendo o caminho natural de
  **conferencia cruzada** do historico. Ficar em `US` mantem essa porta aberta ao
  custo de nada.
- A latencia nao importa: o consumo e' Import mode ([ADR-002](ADR-002-import-mode.md)),
  ou seja, algumas leituras por semana, nao por interacao.
- A camada gratuita do BigQuery e' identica nas duas localizacoes.

## Consequencia
- Se algum dia entrar dado pessoal que exija residencia no Brasil, esta decisao
  tera' de ser revista. Hoje isso nao se aplica: o unico dado sensivel e' o CPF, e
  ele nunca chega ao warehouse ([ADR-007](ADR-007-hash-na-ingestao.md)).
- `RADAR_BQ_LOCATION` continua parametrizavel, para nao travar quem quiser
  reproduzir o projeto em outra regiao.
