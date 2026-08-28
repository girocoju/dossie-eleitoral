/*
  Quem foi eleito PARA UM CARGO TITULAR recebeu votos. Parece obvio, e e' por isso
  que serve de teste: se a juncao entre `consulta_cand` e
  `votacao_candidato_munzona` quebrar — por mudanca no formato do `sq_candidato`,
  por exemplo —, o sintoma seria eleitos sem voto nenhum, em silencio.

  A restricao a TITULAR nao e' detalhe: vice-presidente, vice-governador e os dois
  suplentes de cada senador sao eleitos NA CHAPA e nao recebem votacao propria.
  Conferido em 28/08/2026, e a conta fecha exatamente: em 2022, 27 senadores x 2
  suplentes + 27 vice-governadores + 1 vice-presidente = 82 eleitos sem voto, que
  foi o numero observado. Em 2018, com renovacao de 2/3 do Senado: 54 x 2 + 27 + 1
  = 136, tambem o observado.

  Restrito a eleicoes ja' ocorridas. Tolera ate' 1%: ha' casos de registro
  pos-pleito e de vaga preenchida por suplencia.
*/

with medida as (

    select
        countif(f.votos_nominais is null)                                 as sem_voto,
        count(*)                                                          as eleitos,
        safe_divide(countif(f.votos_nominais is null), count(*)) * 100      as pct
    from {{ ref('fct_candidatura') }} as f
    inner join {{ ref('dim_cargo') }} as g using (cod_cargo)
    where f.foi_eleito
      and g.titular
      and f.ano_eleicao < {{ var('ano_eleicao_atual') }}

)

select *
from medida
where pct > 1
