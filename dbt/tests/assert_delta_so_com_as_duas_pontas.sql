/*
  Constituicao 0.2: `delta_vs_brasil` so' pode existir quando as DUAS variacoes
  existem. Um delta calculado contra comparador ausente seria lido como
  "a UF foi melhor que o Brasil" sem que houvesse Brasil na conta.

  Falha se algum delta estiver preenchido sem as duas variacoes.
*/

select
    sk_mandato,
    cod_indicador,
    variacao_pct,
    variacao_brasil_pct,
    delta_vs_brasil
from {{ ref('fct_mandato_indicador') }}
where delta_vs_brasil is not null
  and (variacao_pct is null or variacao_brasil_pct is null)
