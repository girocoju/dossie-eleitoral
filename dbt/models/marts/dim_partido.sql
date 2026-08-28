{{
  config(
    materialized = 'table',
    description  = 'Partidos com o numero e a federacao vigente em cada eleicao.'
  )
}}

/*
  Grao: (sigla_partido, ano_eleicao). Nao e' "um partido": sigla, numero e nome
  mudam com fusao e incorporacao, e federacao so' existe a partir de 2022. Guardar
  o estado por eleicao e' o que permite ler 2010 com os nomes de 2010.

  Sem nenhuma cor de partido aqui: a paleta do site e' neutra por padrao e a
  cor partidaria so' aparece sob toggle explicito do usuario (Constituicao 0.1).
*/

with base as (

    select
        ano_eleicao,
        sigla_partido,
        nome_partido,
        nr_partido,
        sg_federacao,
        nome_federacao,
        count(*)                                  as n_candidaturas,
        countif(foi_eleito)                       as n_eleitos
    from {{ ref('stg_tse__candidaturas') }}
    where sigla_partido is not null
    group by 1, 2, 3, 4, 5, 6

)

select
    concat(sigla_partido, '-', cast(ano_eleicao as string)) as sk_partido,
    ano_eleicao,
    sigla_partido,
    nome_partido,
    nr_partido,
    sg_federacao,
    nome_federacao,
    sg_federacao is not null                                as em_federacao,
    n_candidaturas,
    n_eleitos
from base
qualify row_number() over (
    partition by sigla_partido, ano_eleicao
    order by n_candidaturas desc
) = 1
