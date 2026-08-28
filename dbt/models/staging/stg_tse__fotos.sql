{{ config(materialized = 'view', description = 'Foto oficial de urna por candidatura (S13, F-13).') }}

/*
  Grao: uma foto por candidatura. A `sk_candidatura` ja' vem montada da ingestao,
  porque o proprio nome do arquivo no pacote do TSE
  (`F{SG_UE}{SQ_CANDIDATO}_div.jpg`) carrega os componentes da chave.

  Aqui nao ha' imagem — so' a URL (ADR-012).
*/

select
    sk_candidatura,
    sq_candidato,
    {{ limpa('sg_ue') }}   as sg_ue,
    ano_eleicao,
    {{ limpa('url_foto') }} as url_foto,
    tamanho_bytes,
    _extracted_at,
    _source_url

from {{ source('raw_tse', 'fotos') }}
where {{ limpa('url_foto') }} is not null
