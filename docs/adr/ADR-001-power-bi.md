# ADR-001 — Power BI em vez de Looker Studio

**Status:** **SUPERSEDIDA pela [ADR-018](ADR-018-site-estatico-em-vez-de-bi.md)** em 28/08/2026
· **Data:** 2026-08-27 · **Origem:** SPEC secao 10

> Esta decisao respondia a pergunta "qual ferramenta de BI". Um dia depois, com o
> lake pronto e a distribuicao definida, a pergunta virou "como isto chega as
> pessoas" — e a resposta deixou de ser uma ferramenta de BI. O *Publish to web*
> nao suporta layout mobile, nao da' URL por candidato e nao e' indexavel pelo
> Google; o Looker Studio tem os mesmos limites. Ver ADR-018.
>
> O registro abaixo fica como estava, porque o raciocinio da epoca era valido para
> a pergunta da epoca.

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
