{{
  config(
    materialized = 'view',
    description  = 'Autorias do Senado, tipadas, com autor principal separado de coautor (F-22).'
  )
}}

/*
  A DISTINCAO QUE A L-20 EXIGIA VIAJA AQUI, E NAO SE PERDE.

  `autor_principal` e' `ordem_assinatura = 1` — o equivalente do `proponente = 1`
  da Camara, validado contra o campo oficial `IndicadorAutorPrincipal` do
  endpoint antigo em 48 comparacoes nas duas direcoes, sem divergencia
  (ver o cabecalho de `ingest/senado.py`).

  As coautorias ficam na view DE PROPOSITO. Elas nao entram na contagem da tela,
  mas sumir com elas aqui tornaria impossivel conferir a separacao — e a L-20
  nasceu justamente do risco de somar apoio como se fosse autoria.
*/

select
    processo_id,
    codigo_materia,
    nullif(identificacao, '')                           as identificacao,
    nullif(sigla, '')                                   as sigla,
    nullif(descricao_sigla, '')                         as descricao_sigla,
    classe_proposicao,
    safe_cast(ano as int64)                             as ano,
    safe_cast(left(data_apresentacao, 10) as date)      as data_apresentacao,
    tramitando,

    safe_cast(codigo_parlamentar as int64)              as id_casa,
    nullif(nome_autor, '')                              as nome_autor,
    safe_cast(ordem_assinatura as int64)                as ordem_assinatura,
    coalesce(autor_principal, false)                    as autor_principal,
    nullif(sigla_partido, '')                           as sigla_partido_autor,
    nullif(sg_uf, '')                                   as sigla_uf_autor,

    _extracted_at

from {{ source('raw_legislativo', 'senado_autoria') }}
where codigo_parlamentar is not null
  and ano is not null
