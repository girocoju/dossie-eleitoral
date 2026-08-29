{{
  config(
    materialized = 'table',
    cluster_by   = ['sk_candidatura', 'doador_tipo'],
    description  = 'Quem financiou cada candidatura, agregado por doador (F-11).'
  )
}}

/*
  Grao: (sk_candidatura, sk_doador). Uma linha por doador de cada candidatura,
  ja' somando as doacoes repetidas da mesma origem.

  E' o modelo que responde "quem sustenta esta campanha" — a pergunta que a
  prestacao de contas existe para responder, e que a lista crua de 43 mil
  lancamentos nao responde: um doador que fez 50 transferencias aparece 50 vezes e
  parece 50 pessoas.

  A IDENTIDADE DO DOADOR E' `sk_doador`, NUNCA O NOME. Nome agrupa homonimos como
  se fossem a mesma pessoa — o mesmo erro que a ponte do Senado quase cometeu com
  parlamentar (ADR-014). Aqui a chave e' CNPJ quando empresa e hash de CPF quando
  pessoa fisica: distingue sem expor.

  O CNPJ FICA LEGIVEL de proposito. Nao e' dado pessoal — identifica empresa,
  partido ou comite, e e' exatamente o que permite ver que a mesma empresa
  financiou candidaturas de partidos diferentes. Tratar CNPJ como CPF confundiria
  privacidade de pessoa com opacidade de empresa (ADR-020).

  RANKING DE DOADOR NAO E' RANKING DE POLITICO. A Constituicao 0.1 proibe ordenar
  POLITICOS por metrica. Ordenar os doadores DE UM candidato pelo valor e' o
  oposto disso: e' fiscalizacao de quem paga, nao placar de quem recebe. A tela
  ordena dentro da ficha; nunca compara fichas entre si.
*/

with receitas as (

    select * from {{ ref('stg_tse__financiamento') }}
    where sk_doador is not null

)

select
    sk_candidatura,
    sk_doador,
    any_value(ano_eleicao)                    as ano_eleicao,
    any_value(cod_cargo)                      as cod_cargo,

    -- O nome vem do maior lancamento, nao de `any_value`: se a mesma identidade
    -- aparece com grafias diferentes, a que acompanha o maior valor e' a que o
    -- leitor tem mais chance de reconhecer.
    array_agg(nome_doador order by valor desc limit 1)[safe_offset(0)] as nome_doador,

    any_value(doador_tipo)                    as doador_tipo,
    -- Fica NULL quando pessoa fisica. O hash NAO vai junto: ele serve para
    -- agrupar dentro do mart, nao para aparecer numa tela.
    any_value(doador_cnpj)                    as doador_cnpj,
    any_value(doador_uf)                      as doador_uf,
    any_value(doador_ramo)                    as doador_ramo,

    sum(valor)                                as vl_doado,
    count(*)                                  as qt_doacoes,
    min(data_receita)                         as dt_primeira_doacao,
    max(data_receita)                         as dt_ultima_doacao,

    -- Doador que tambem e' candidato. Quando e' o PROPRIO candidato da linha, e'
    -- recurso proprio; quando e' outro, e' repasse entre candidaturas — 434
    -- lancamentos em 2026, o material mais analitico do pacote.
    logical_or(e_autofinanciamento)           as e_o_proprio_candidato,
    any_value(doador_sq_candidato)            as doador_sq_candidato,
    max(_extracted_at)                        as _extracted_at

from receitas
group by sk_candidatura, sk_doador
