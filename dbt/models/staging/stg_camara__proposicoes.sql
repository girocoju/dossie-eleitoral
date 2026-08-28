{{
  config(
    materialized = 'view',
    description  = 'Proposicoes da Camara em que um deputado e proponente, tipadas (F-16).'
  )
}}

/*
  O filtro que mais importa ja' aconteceu na ingestao: so' entram linhas com
  `proponente = 1`. A Camara registra como "autor" todo mundo que assina, e em
  2025 isso significou 21,4% de apoio misturado com autoria — num requerimento
  com 264 assinaturas, 263 eram apoio.

  `total_assinantes` fica visivel de proposito. Um projeto com 1 assinante e um
  com 264 nao dizem a mesma coisa sobre quem propos, e esconder esse numero
  devolveria pela porta dos fundos a confusao que o filtro de proponente evitou.
*/

select
    id_proposicao,
    ano,
    sigla_tipo,
    descricao_tipo,
    classe_proposicao,
    numero,
    ementa,
    safe_cast(left(data_apresentacao, 10) as date)      as data_apresentacao,
    nullif(situacao, '')                                as situacao,
    nullif(tramitacao, '')                              as tramitacao,
    nullif(sigla_orgao, '')                             as sigla_orgao,
    arquivada,
    virou_norma,
    situacao_conhecida,
    nullif(url_inteiro_teor, '')                        as url_inteiro_teor,
    id_deputado,
    nome_autor,
    nullif(sigla_partido_autor, '')                     as sigla_partido_autor,
    nullif(sigla_uf_autor, '')                          as sigla_uf_autor,
    safe_cast(ordem_assinatura as int64)                as ordem_assinatura,
    total_assinantes,
    _extracted_at
from {{ source('raw_legislativo', 'proposicoes') }}
where id_deputado is not null
  and id_deputado != ''
