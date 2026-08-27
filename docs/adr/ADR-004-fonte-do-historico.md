# ADR-004 — CSV do TSE como fonte unica; Base dos Dados so' para conferencia

**Status:** Aceita (era Pendente no SPEC) · **Data:** 2026-08-27 · **Task:** T-201

## Contexto
O SPEC (S12) sugere a Base dos Dados como atalho para o historico 1998-2022, ja'
tratado e disponivel no BigQuery. A alternativa e' baixar os CSVs do TSE para
todos os anos, com o mesmo codigo que ja' e' obrigatorio para 2026 — porque 2026
ainda nao existe na Base dos Dados.

## Decisao
Os oito anos (1998-2026) vem do CSV do TSE, pelo mesmo `ingest/tse.py`.
A Base dos Dados fica como fonte de **conferencia cruzada**, nao de carga.

## Motivo
- **Um caminho de codigo, nao dois.** 2026 obriga a existencia do leitor de CSV.
  Usar a Base dos Dados para o historico significaria manter duas ingestoes, duas
  formas de erro e dois vocabularios de coluna.
- **Custo.** Ler a Base dos Dados consome a cota de query do free tier; baixar do
  CDN do TSE nao consome nada da cota.
- **Reprodutibilidade (Constituicao secao 4).** O download grava sha256 e
  `_extracted_at` de cada pacote. Depender de uma tabela de terceiro reprocessada
  fora do nosso controle enfraquece isso.
- **Layout.** O tratamento da Base dos Dados esconderia justamente as diferencas
  de layout entre anos que o projeto precisa enxergar
  ([ADR-008](ADR-008-layout-declarativo.md)).

## Consequencia
- Mais trabalho por ano: cada um exige `verify-layout` antes da primeira carga.
- Em compensacao, a divergencia entre a nossa leitura e a Base dos Dados vira um
  teste possivel, e nao um ponto cego.
- A localizacao `US` ([ADR-003](ADR-003-localizacao-bigquery.md)) foi mantida
  exatamente para essa conferencia continuar barata.
