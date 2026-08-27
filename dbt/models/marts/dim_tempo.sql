{{
  config(
    materialized = 'table',
    description  = 'Calendario anual do projeto: liga indicadores anuais a eleicoes e mandatos.'
  )
}}

/*
  Grao: um ano. Cobre de 1980 (inicio da serie de homicidios do Atlas da Violencia,
  a mais longa do projeto) ao ano corrente.

  `ano_eleicao_anterior` e' o que permite ao Power BI responder "de que mandato
  este ano faz parte" sem calculo no visual.
*/

with anos as (

    select ano
    from unnest(generate_array(1980, extract(year from current_date()))) as ano

),

eleicoes as (

    select eleicao
    from unnest({{ var('anos_eleicao') }}) as eleicao

)

select
    a.ano,
    date(a.ano, 1, 1)                                   as data_inicio_ano,
    date(a.ano, 12, 31)                                 as data_fim_ano,
    a.ano in unnest({{ var('anos_eleicao') }})          as is_ano_eleicao,
    (select max(eleicao) from eleicoes where eleicao <= a.ano)      as ano_eleicao_anterior,
    (select min(eleicao) from eleicoes where eleicao >= a.ano)      as ano_eleicao_seguinte,
    cast(floor((a.ano - 1) / 10) * 10 as int64)         as decada
from anos as a
