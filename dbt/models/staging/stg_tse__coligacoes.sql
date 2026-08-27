{{ config(materialized = 'view', description = 'Coligacoes e federacoes por cargo e UE (S5).') }}

select
    ano_eleicao,
    {{ limpa('sq_coligacao') }}           as sq_coligacao,
    {{ limpa('sg_uf') }}                  as sg_uf,
    {{ limpa('sg_ue') }}                  as sg_ue,
    {{ inteiro('cod_cargo') }}            as cod_cargo,
    {{ limpa('tp_agremiacao') }}          as tp_agremiacao,
    {{ limpa('sigla_partido') }}          as sigla_partido,
    {{ limpa('nome_coligacao') }}         as nome_coligacao,
    {{ limpa('composicao_coligacao') }}   as composicao_coligacao,
    _extracted_at,
    _source_url

from {{ source('raw_tse', 'coligacoes') }}
where {{ limpa('sq_coligacao') }} is not null
