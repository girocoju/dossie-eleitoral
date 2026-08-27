/*
  Constituicao 0.2 + SPEC 2.2: o modulo "Durante o mandato" existe SO' para
  Presidente e Governador. Se um deputado ou senador vazar para ca', o vinculo
  individuo <-> indicador regional que o SPEC recusou volta pela porta dos fundos.

  Falha se aparecer qualquer cargo fora de `cargos_mandato_executivo`.
*/

select
    f.cod_indicador,
    f.cod_cargo,
    count(*) as linhas
from {{ ref('fct_mandato_indicador') }} as f
where f.cod_cargo not in unnest({{ var('cargos_mandato_executivo') }})
group by 1, 2
