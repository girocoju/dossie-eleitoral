{{
  config(
    materialized = 'table',
    cluster_by   = ['sg_uf', 'cod_cargo', 'ano_eleicao'],
    description  = 'Votos por municipio para Presidente e Governador. Base do mapa eleitoral.'
  )
}}

/*
  Grao: candidatura x turno x municipio.

  RESTRITO a Presidente (1) e Governador (3), por decisao de escopo. Com os
  cargos proporcionais, seriam ~70 milhoes de linhas somando as sete eleicoes —
  dezenas de milhares de candidatos a deputado, cada um com votos espalhados por
  centenas de municipios. Restrito ao executivo majoritario, fica na casa das
  centenas de milhares, o que cabe numa carga unica diaria (ADR-002, ADR-018).

  E' tambem onde o mapa municipal significa alguma coisa: presidente e governador
  sao eleitos por maioria num territorio, e a distribuicao geografica do voto e'
  informacao de verdade. Para deputado, o mapa seria ruido.

  `pct_do_municipio` e' a participacao do candidato no total valido daquele
  municipio — e' isso, e nao o numero absoluto, que torna municipios de tamanhos
  diferentes comparaveis num mapa.
*/

with votos as (

    select
        ano_eleicao,
        {{ limpa('sg_uf') }}                   as sg_uf,
        {{ limpa('cd_municipio') }}            as cd_municipio,
        {{ limpa('nm_municipio') }}            as nm_municipio,
        {{ inteiro('cod_cargo') }}             as cod_cargo,
        sq_candidato,
        {{ inteiro('nr_turno') }}              as nr_turno,
        if({{ inteiro('cod_cargo') }} = 1, 'BR', {{ limpa('sg_uf') }}) as sg_ue,
        if(
            coalesce(qt_votos_nominais, 0) > 0,
            qt_votos_nominais,
            qt_votos_nominais_validos
        )                                      as votos_nominais,
        _extracted_at
    from {{ source('raw_tse', 'votacao_municipio') }}
    where sq_candidato is not null
      and {{ limpa('cd_municipio') }} is not null

)

select
    {{ sk_candidatura(ano_eleicao='v.ano_eleicao', sg_ue='v.sg_ue', sq_candidato='v.sq_candidato') }}
                                               as sk_candidatura,
    v.ano_eleicao,
    v.sg_uf,
    u.regiao,
    v.cd_municipio,
    v.nm_municipio,
    v.cod_cargo,
    v.nr_turno,
    d.nome_urna,
    d.sigla_partido,
    v.votos_nominais,

    -- participacao no municipio: e' o que torna municipios de tamanhos
    -- diferentes comparaveis num mapa
    safe_divide(
        v.votos_nominais,
        sum(v.votos_nominais) over (
            partition by v.ano_eleicao, v.cd_municipio, v.cod_cargo, v.nr_turno
        )
    ) * 100                                    as pct_do_municipio,

    v._extracted_at
from votos as v
left join {{ ref('dim_uf') }} as u
       on u.sg_uf = v.sg_uf
left join {{ ref('dim_candidato') }} as d
       on d.sk_candidatura = {{ sk_candidatura(ano_eleicao='v.ano_eleicao', sg_ue='v.sg_ue', sq_candidato='v.sq_candidato') }}
