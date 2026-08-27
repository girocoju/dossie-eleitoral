/*
  F-05, criterio de aceite: `fct_mandato` cobre 100% dos governadores e presidentes
  eleitos entre 1998 e 2022.

  Cada eleicao geral elege 1 Presidente e 27 Governadores. A checagem e' feita
  contra o proprio staging (quantos "eleitos" a fonte declara) e nao contra um
  numero digitado, para nao inventar verdade: se o TSE publicar 26 governadores
  num ano, o teste aponta a divergencia entre staging e mart, que e' o erro que
  este teste procura.
*/

with na_fonte as (

    select
        ano_eleicao,
        cod_cargo,
        count(distinct sq_candidato) as eleitos_fonte
    from {{ ref('stg_tse__candidaturas') }}
    where foi_eleito
      and cod_cargo in (1, 3)
      and ano_eleicao between 1998 and 2022
    group by 1, 2

),

no_mart as (

    select
        ano_eleicao,
        cod_cargo,
        count(distinct sq_candidato) as eleitos_mart
    from {{ ref('fct_mandato') }}
    where cod_cargo in (1, 3)
      and ano_eleicao between 1998 and 2022
    group by 1, 2

)

select
    f.ano_eleicao,
    f.cod_cargo,
    f.eleitos_fonte,
    coalesce(m.eleitos_mart, 0) as eleitos_mart
from na_fonte as f
left join no_mart as m using (ano_eleicao, cod_cargo)
where coalesce(m.eleitos_mart, 0) != f.eleitos_fonte
