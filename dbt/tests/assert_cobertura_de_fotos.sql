/*
  F-13, criterio de aceite: `tem_foto` verdadeiro em ao menos 95% das candidaturas
  de 2026.

  O piso NAO existe para checar se candidato tem foto — existe para detectar
  mudanca de nomenclatura na fonte. O TSE nomeia cada imagem como
  `F{SG_UE}{SQ_CANDIDATO}_div.jpg`; se esse padrao mudar, a juncao para de casar e
  a cobertura despenca de uma vez. Medido em 27/08/2026 no pacote do Acre: 385 de
  387 candidaturas (99,5%), zero fotos sem candidatura correspondente.

  Falha quando a cobertura fica abaixo de 95%.
*/

with medida as (

    select
        countif(tem_foto)                                   as com_foto,
        count(*)                                            as total,
        safe_divide(countif(tem_foto), count(*)) * 100       as pct
    from {{ ref('dim_candidato') }}
    where ano_eleicao = {{ var('ano_eleicao_atual') }}

)

select *
from medida
where pct < 95
