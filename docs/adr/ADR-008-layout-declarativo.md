# ADR-008 — Layout do TSE declarado em YAML e resolvido contra o header real

**Status:** Aceita · **Data:** 2026-08-27 · **Origem:** SPEC secao 12, risco 1

## Contexto
O layout do `consulta_cand` muda entre anos, e nao so' um pouco. A conferencia do
pacote real de 2026 (27/08/2026) mostrou que o TSE **partiu o cadastro em dois
arquivos**: `consulta_cand` ficou com 50 colunas e `consulta_cand_complementar`
levou outras 49, incluindo `ST_REELEICAO`, `VR_DESPESA_MAX_CAMPANHA` e a situacao
de julgamento. Um leitor que assumisse o layout de 2022 teria lido 2026 com
metade dos campos silenciosamente nulos.

## Decisao
Nenhum nome de coluna aparece em `.py`. Cada ano tem um `ingest/layouts/tse_{ano}.yml`
que declara, por campo canonico, a lista de nomes aceitos. Na leitura:

1. o header real e' lido do CSV;
2. cada campo e' resolvido pela lista de aliases;
3. campo **obrigatorio** que nao resolve -> a carga **falha**, apontando o `leiame.pdf`;
4. campo **opcional** que nao resolve -> NULL;
5. coluna da fonte nao mapeada -> vai para `_extras` (JSON), nunca e' descartada.

`python -m ingest.tse verify-layout --ano X` roda so' a resolucao e imprime o diff.

## Motivo
- Transforma "o TSE mudou o layout" de bug silencioso em falha ruidosa com
  instrucao de correcao.
- O flag `verificado: true/false` no YAML separa o que foi conferido contra o
  arquivo real do que ainda e' expectativa.
- `_extras` garante que uma coluna nova nao seja perdida antes de alguem decidir
  o que fazer com ela.

## Consequencia
- Um ano novo exige rodar `verify-layout` antes da primeira carga. E' proposital.
- Hoje so' 2026 esta' com `verificado: true`. Os demais anos estao listados em
  `docs/LACUNAS.md`.
