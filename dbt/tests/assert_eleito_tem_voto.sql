/*
  Quem foi eleito recebeu votos. Parece obvio, e e' exatamente por isso que serve
  de teste: se a juncao entre `consulta_cand` e `votacao_candidato_munzona`
  quebrar — por mudanca no formato do `sq_candidato`, por exemplo —, o sintoma
  seria eleitos sem voto nenhum, em silencio.

  Restrito a eleicoes ja' ocorridas. Tolera ate' 1% de eleitos sem voto: o TSE tem
  casos de registro pos-pleito e de vaga preenchida por suplencia.
*/

with medida as (

    select
        countif(votos_nominais is null)                                   as sem_voto,
        count(*)                                                          as eleitos,
        safe_divide(countif(votos_nominais is null), count(*)) * 100       as pct
    from {{ ref('fct_candidatura') }}
    where foi_eleito
      and ano_eleicao < {{ var('ano_eleicao_atual') }}

)

select *
from medida
where pct > 1
