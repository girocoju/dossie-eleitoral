{{
  config(
    materialized = 'view',
    description  = 'Assentos de senador em colegiado, tipados e classificados (F-29). Fecha a L-28.'
  )
}}

/*
  Uma linha por (senador, colegiado, periodo). O mesmo senador reaparece no mesmo
  colegiado a cada renovacao, e isso e' fato: sao mandatos distintos ali.

  ── SAO DUAS ROTAS DA FONTE, JA' UNIDAS NA INGESTAO ──

  `origem_do_vinculo` diz de qual:

      comissoes   quem SENTOU — Titular, Suplente, Nato
      cargos      quem COMANDOU — Presidente, Vice, Relator, Secretario

  A segunda traz colegiado que a primeira nao conhece, a Mesa Diretora inclusive.
  Por isso as duas sao unidas e nao cruzadas: juntar por chave perderia o assento
  mais visivel do pais. Ver ADR-049, que fecha a L-30.

  ── A CLASSE NAO E' CALCULADA AQUI, E VEM DE DUAS PROCEDENCIAS ──

  Como na Camara (ADR-044), ela chega pronta da ingestao. A diferenca e' que o
  catalogo do Senado so' lista colegiado EM ATIVIDADE: medido em 05/09/2026, 292
  colegiados citados pelos senadores nao estavam nele, e nao ha' rota de detalhe
  que os resolva.

  Sobrou o NOME OFICIAL por extenso. `origem_da_classe` diz de onde veio o tipo:

      catalogo   veio do `CodigoTipoColegiado` da fonte
      nome       deduzido da forma oficial escrita por extenso
      nenhuma    nao foi possivel, e o vinculo NAO entra na ficha

  A distincao viaja ate' a tela em vez de ser apagada aqui. Ver ADR-048.
*/

select
    codigo_parlamentar,
    codigo_colegiado,
    nullif(sigla_colegiado, '')                         as sigla_colegiado,
    nullif(nome_colegiado, '')                          as nome_colegiado,
    nullif(casa_colegiado, '')                          as casa_colegiado,
    cod_tipo_colegiado,
    classe_colegiado,
    tipo_colegiado,
    origem_da_classe,
    origem_do_vinculo,
    nullif(papel, '')                                   as papel,

    safe_cast(nullif(data_inicio, '') as date)          as data_inicio,
    -- Vinculo sem data de fim esta' EM CURSO. Preencher com a data de hoje faria
    -- a tela dizer que terminou hoje, todo dia (Regra 5).
    safe_cast(nullif(data_fim, '') as date)             as data_fim,
    nullif(data_fim, '') is null                        as em_curso,

    _extracted_at

from {{ source('raw_legislativo', 'senado_comissoes') }}
where codigo_parlamentar is not null
  and codigo_colegiado is not null
