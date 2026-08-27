# Layouts do TSE

O layout dos CSVs do TSE **muda entre anos** (SPEC §12, risco 1). Estes arquivos
declaram, para cada campo canonico do projeto, **quais nomes de coluna sao aceitos**.

O loader (`ingest/tse.py`) **nunca adivinha**:

1. le o cabecalho real do CSV;
2. resolve cada campo canonico contra a lista de `aliases`;
3. se um campo listado em `obrigatorios` nao resolver, **falha** apontando o `leiame.pdf` do ano;
4. campos opcionais que nao resolvem viram `NULL` (ex.: `cor_raca` so' existe a partir de 2014);
5. colunas da fonte que nao foram mapeadas **nao sao descartadas** — vao para a coluna
   `_extras` (JSON) da tabela `raw`, preservando a copia fiel exigida pelo SPEC §4.

## Como conferir um ano

```bash
python -m ingest.tse verify-layout --ano 2026
```

Imprime, por dataset: header real, campos resolvidos, obrigatorios faltando e colunas
extras. Atualize o YAML do ano com base no `leiame.pdf` — nunca hardcode nome de coluna
em `.py`.

## Herança

`tse_{ano}.yml` traz `extends: tse_base.yml`. O merge e' por dataset e por campo:
o ano sobrescreve apenas o que declara.
