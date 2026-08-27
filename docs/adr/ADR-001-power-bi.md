# ADR-001 — Power BI em vez de Looker Studio

**Status:** Aceita · **Data:** 2026-08-27 · **Origem:** SPEC secao 10

## Contexto
O produto e' peca de portfolio da Data Duba Intelligence, dirigida a recrutadores
e clientes corporativos. As opcoes praticas sobre BigQuery sao Looker Studio
(gratuito, web) e Power BI Desktop.

## Decisao
Power BI, com o arquivo salvo no formato de projeto `.pbip`.

## Motivo
- Conector nativo para BigQuery, com Import mode de verdade.
- `.pbip` e' texto (TMDL + JSON) e portanto versionavel no Git — um `.pbix` seria
  um binario opaco, incompativel com a Constituicao secao 6.
- E' a ferramenta que o publico-alvo corporativo usa; o artefato em si demonstra
  a competencia que o portfolio quer demonstrar.

## Consequencia
- Exige Power BI Desktop (Windows) para editar. O modelo semantico em TMDL pode
  ser lido e revisado em qualquer editor de texto.
- A publicacao depende do Power BI Service (*Publish to web*), que expoe o
  relatorio publicamente sem autenticacao — aceitavel porque todo o dado ja' e'
  publico e agregado.
