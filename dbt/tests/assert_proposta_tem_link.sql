/*
  F-14: toda candidatura com proposta precisa do link para a fonte oficial.

  O produto NAO hospeda o PDF (ADR-013) — o link e' a unica forma de o leitor
  chegar ao documento. Uma linha com `tem_proposta_governo = true` e sem
  `url_proposta_oficial` seria um disclaimer que afirma algo sem deixar conferir.
*/

select
    sk_candidatura,
    cod_cargo,
    sg_ue,
    nome_arquivo_proposta
from {{ ref('fct_candidatura') }}
where tem_proposta_governo
  and url_proposta_oficial is null
