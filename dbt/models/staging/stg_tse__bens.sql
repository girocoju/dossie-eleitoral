{{ config(materialized = 'view', description = 'Bens declarados por candidatura, tipados (S2).') }}

/*
  Grao: um bem declarado. A soma por candidatura vive em `fct_candidatura`, nao aqui —
  assim quem quiser a distribuicao de tipos de bem ainda tem a linha original.

  `valor_bem` passa por `decimal_br` porque o TSE grava `1.234,56` neste arquivo
  (ao contrario de VR_DESPESA_MAX_CAMPANHA, que em 2026 veio com ponto decimal).
*/

select
    {{ sk_candidatura() }} as sk_candidatura,
    ano_eleicao,
    sq_candidato,
    {{ inteiro('nr_ordem_bem') }}        as nr_ordem_bem,
    {{ limpa('sg_uf') }}                 as sg_uf,
    {{ limpa('sg_ue') }}                 as sg_ue,
    {{ inteiro('cd_tipo_bem') }}         as cd_tipo_bem,
    {{ limpa('ds_tipo_bem') }}           as tipo_bem,
    {{ limpa('ds_bem') }}                as descricao_bem,
    {{ decimal_br('valor_bem') }}        as valor_bem,
    _extracted_at,
    _source_url

from {{ source('raw_tse', 'bens') }}
where sq_candidato is not null
