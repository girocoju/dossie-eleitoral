{{
  config(
    materialized = 'view',
    description  = 'Candidaturas do TSE 1998-2026 com schema unico, tipado e limpo (F-03).'
  )
}}

/*
  F-03 — schema unico apesar da variacao de layout por ano.

  Duas decisoes que valem comentario:

  1. O grao aqui continua sendo (sq_candidato, ano_eleicao, nr_turno) — uma linha por
     turno, como na fonte. O achatamento para "uma candidatura" acontece so' em
     `fct_candidatura`, porque quem quiser olhar 2o turno precisa das duas linhas.

  2. Em 2026 o TSE moveu situacao de julgamento, reeleicao e despesa maxima para o
     arquivo complementar. O LEFT JOIN abaixo recompoe o registro completo; para os
     anos em que essas colunas estavam no arquivo principal, o COALESCE mantem o
     valor de la'. Nenhum dos dois lados e' obrigatorio.
*/

with candidatos as (

    select * from {{ source('raw_tse', 'candidatos') }}

),

complementar as (

    select * from {{ source('raw_tse', 'complementar') }}

),

junto as (

    select
        c.ano_eleicao,
        c.sq_candidato,
        {{ inteiro('c.nr_turno') }}                        as nr_turno,
        {{ inteiro('c.cod_cargo') }}                       as cod_cargo,
        {{ limpa('c.ds_cargo') }}                          as ds_cargo,
        {{ limpa('c.sg_uf') }}                             as sg_uf,
        {{ limpa('c.sg_ue') }}                             as sg_ue,
        {{ limpa('c.nm_ue') }}                             as nm_ue,
        {{ limpa('c.tp_abrangencia') }}                    as tp_abrangencia,
        {{ inteiro('c.cd_eleicao') }}                      as cd_eleicao,
        {{ limpa('c.ds_eleicao') }}                        as ds_eleicao,
        {{ data_br('c.dt_eleicao') }}                      as data_eleicao,

        -- pessoa
        c.cpf_hash,
        {{ limpa('c.nome_completo') }}                     as nome_completo,
        {{ limpa('c.nome_urna') }}                         as nome_urna,
        {{ limpa('c.nome_social') }}                       as nome_social,
        {{ data_br('c.data_nascimento') }}                 as data_nascimento,
        {{ limpa('c.sg_uf_nascimento') }}                  as sg_uf_nascimento,
        {{ limpa('c.genero') }}                            as genero,
        {{ limpa('c.cor_raca') }}                          as cor_raca,
        {{ limpa('c.grau_instrucao') }}                    as grau_instrucao,
        {{ limpa('c.estado_civil') }}                      as estado_civil,
        {{ limpa('c.ocupacao') }}                          as ocupacao,

        -- partido / agremiacao
        {{ inteiro('c.nr_candidato') }}                    as nr_candidato,
        {{ inteiro('c.nr_partido') }}                      as nr_partido,
        {{ limpa('c.sigla_partido') }}                     as sigla_partido,
        {{ limpa('c.nome_partido') }}                      as nome_partido,
        {{ limpa('c.tp_agremiacao') }}                     as tp_agremiacao,
        {{ limpa('c.sq_coligacao') }}                      as sq_coligacao,
        {{ limpa('c.nome_coligacao') }}                    as nome_coligacao,
        {{ limpa('c.composicao_coligacao') }}              as composicao_coligacao,
        {{ limpa('c.sg_federacao') }}                      as sg_federacao,
        {{ limpa('c.nome_federacao') }}                    as nome_federacao,

        -- situacao: o arquivo principal em anos antigos, o complementar em 2026
        {{ limpa('c.situacao_candidatura') }}              as situacao_candidatura,
        {{ limpa('x.situacao_julgamento') }}               as situacao_julgamento,
        coalesce({{ limpa('c.situacao_turno') }}, {{ limpa('x.situacao_turno') }})
                                                           as situacao_turno,
        coalesce({{ sim_nao('c.st_reeleicao') }}, {{ sim_nao('x.st_reeleicao') }})
                                                           as reeleicao_declarada,
        coalesce({{ sim_nao('c.st_declarar_bens') }}, {{ sim_nao('x.st_declarar_bens') }})
                                                           as declarou_bens,
        coalesce(
            {{ decimal_br('c.vr_despesa_max_campanha') }},
            {{ decimal_br('x.vr_despesa_max_campanha') }}
        )                                                  as despesa_max_campanha,
        {{ limpa('x.ds_situacao_cassacao') }}              as situacao_cassacao,
        {{ limpa('x.ds_etnia_indigena') }}                 as etnia_indigena,
        {{ sim_nao('x.st_quilombola') }}                   as quilombola,

        c._extracted_at,
        c._source_url,
        c._source_file

    from candidatos as c
    left join complementar as x
      on  c.sq_candidato = x.sq_candidato
      and c.ano_eleicao  = x.ano_eleicao

)

select
    *,
    -- eleito e' derivado uma unica vez, aqui, e reaproveitado por todo o resto
    {{ foi_eleito('situacao_turno') }} as foi_eleito
from junto
where sq_candidato is not null
