{{
  config(
    materialized = 'view',
    description  = 'Assentos de deputado em orgao da Camara, tipados e classificados (F-26).'
  )
}}

/*
  Uma linha por (deputado, orgao, periodo). O mesmo deputado reaparece na mesma
  comissao a cada renovacao anual, e isso e' fato: sao mandatos distintos naquele
  colegiado.

  ── A CLASSE NAO E' CALCULADA AQUI ──

  Ela vem pronta da ingestao, derivada do `codTipoOrgao` oficial da Camara. Nao e'
  duplicacao evitavel: recalcular no SQL exigiria repetir o mapa de 40 codigos, e
  duas copias divergem no dia em que a Camara criar um tipo novo — que foi
  exatamente o problema que a L-20 documentou noutro contexto (ADR-034).

  ── FILIACAO PARTIDARIA NAO E' COMISSAO, E CONTINUA AQUI ──

  Partido, bloco, lideranca e bancada tambem sao "orgao" na API. Eles chegam
  classificados como `partidaria` e NAO sao descartados: o dado fica no lake para
  quem quiser outra tela depois. Quem separa e' quem consome — `fct_comissao_deputado`
  so' promove o que e' colegiado.
*/

select
    id_deputado,
    id_orgao,
    nullif(sigla_orgao, '')                             as sigla_orgao,
    nullif(nome_orgao, '')                              as nome_orgao,
    cod_tipo_orgao,
    classe_orgao,
    tipo_orgao,
    nullif(papel, '')                                   as papel,
    cod_papel,

    safe_cast(nullif(data_inicio, '') as date)          as data_inicio,
    -- Vinculo sem data de fim esta' EM CURSO. Preencher com a data de hoje
    -- faria a tela dizer que terminou hoje, todo dia (Regra 5).
    safe_cast(nullif(data_fim, '') as date)             as data_fim,
    nullif(data_fim, '') is null                        as em_curso,

    _extracted_at

from {{ source('raw_legislativo', 'camara_comissoes') }}
where id_deputado is not null
  and id_orgao is not null
