{{ config(materialized = 'view', description = 'Vagas em disputa por cargo e unidade eleitoral (S5).') }}

select
    ano_eleicao,
    {{ limpa('sg_uf') }}      as sg_uf,
    {{ limpa('sg_ue') }}      as sg_ue,
    {{ limpa('nm_ue') }}      as nm_ue,
    {{ inteiro('cod_cargo') }} as cod_cargo,
    {{ limpa('ds_cargo') }}   as ds_cargo,
    {{ inteiro('qt_vagas') }} as qt_vagas,
    {{ data_br('dt_posse') }} as data_posse,
    _extracted_at,
    _source_url

from {{ source('raw_tse', 'vagas') }}
where {{ inteiro('qt_vagas') }} is not null
