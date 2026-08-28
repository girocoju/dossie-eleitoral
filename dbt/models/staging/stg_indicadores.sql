{{
  config(
    materialized = 'view',
    description  = 'Indicadores socioeconomicos de todas as fontes no mesmo formato longo (F-04).'
  )
}}

/*
  Une IBGE/SIDRA, IPEA/Ipeadata, Tesouro (SICONFI e RTN) e INEP/IDEB no grao
  (cod_indicador, sg_uf, ano).

  A deduplicacao existe porque a ingestao e' idempotente mas nao transacional: se
  uma carga cair no meio e for repetida, pode haver duas extracoes do mesmo ponto.
  Fica a mais recente por `_extracted_at` — a fonte mais nova ganha, sempre.
*/

with fontes as (

    select
        cod_indicador,
        sg_uf,
        ano,
        valor,
        unidade,
        fonte,
        n_periodos,
        _extracted_at,
        _source_url
    from {{ source('raw_ibge', 'indicadores') }}

    union all

    select
        cod_indicador,
        sg_uf,
        ano,
        valor,
        unidade,
        fonte,
        n_periodos,
        _extracted_at,
        _source_url
    from {{ source('raw_ipea', 'indicadores') }}

    union all

    select
        cod_indicador,
        sg_uf,
        ano,
        valor,
        unidade,
        fonte,
        n_periodos,
        _extracted_at,
        _source_url
    from {{ source('raw_tesouro', 'indicadores') }}

    union all

    select
        cod_indicador,
        sg_uf,
        ano,
        valor,
        unidade,
        fonte,
        n_periodos,
        _extracted_at,
        _source_url
    from {{ source('raw_inep', 'indicadores') }}

    union all

    select
        cod_indicador,
        sg_uf,
        ano,
        valor,
        unidade,
        fonte,
        n_periodos,
        _extracted_at,
        _source_url
    from {{ source('raw_tesouro', 'rtn') }}

)

select
    cod_indicador,
    sg_uf,
    ano,
    valor,
    unidade,
    fonte,
    n_periodos,
    _extracted_at,
    _source_url
from fontes
where valor is not null
  and sg_uf is not null
  and ano between 1980 and extract(year from current_date())
qualify row_number() over (
    partition by cod_indicador, sg_uf, ano
    order by _extracted_at desc
) = 1
