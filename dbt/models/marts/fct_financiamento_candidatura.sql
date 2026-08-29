{{
  config(
    materialized = 'table',
    cluster_by   = ['sk_candidatura', 'origem_recurso'],
    description  = 'Receita de campanha por candidatura e origem do recurso (F-11).'
  )
}}

/*
  Grao: (sk_candidatura, origem_recurso).

  A ORIGEM FAZ PARTE DA CHAVE. Um total isolado — "R$ 42 milhoes" — esconde a
  unica coisa que o dado responde bem: de ONDE veio. Conferido em 2026:

    Recursos de partido politico     R$ 3.292,4 mi   em 12.497 lancamentos
    Recursos de pessoas fisicas      R$   174,6 mi   em 21.377 lancamentos

  Ou seja, 92% do dinheiro de campanha do pais e' fundo partidario/eleitoral, e
  quase metade dos lancamentos e' doacao de pessoa fisica de valor pequeno. Uma
  campanha de R$ 40 milhoes toda do partido e uma de R$ 40 milhoes vinda de 3 mil
  pessoas sao fatos politicos opostos, e o total sozinho nao distingue.

  DIFERENTE de `fct_atividade_legislativa`, aqui somar as linhas E' valido: sao
  parcelas do mesmo dinheiro. A camada de apresentacao soma para o numero de topo
  e mostra a quebra logo abaixo.

  O QUE ESTE MODELO NAO TEM: ranking. Nao existe coluna de posicao, nem
  ordenacao por valor gravada. Lista de politico ordenada por dinheiro arrecadado
  e' placar (Constituicao 0.1) — e arrecadar muito nao e' merito nem demerito.
  O valor aparece na ficha de cada um, ao lado do limite legal do cargo.

  AUSENCIA NAO E' ZERO. So' entram candidaturas que declararam. Quem nao esta'
  aqui nao declarou zero: nao declarou. O prazo de prestacao vai ate' depois de
  04/10/2026 e a cobertura vai crescer.
*/

with receitas as (

    select * from {{ ref('stg_tse__financiamento') }}

)

select
    sk_candidatura,
    coalesce(origem_recurso, 'nao informada')      as origem_recurso,
    any_value(ano_eleicao)                         as ano_eleicao,
    any_value(sg_uf)                               as sg_uf,
    any_value(cod_cargo)                           as cod_cargo,
    any_value(sigla_partido)                       as sigla_partido,

    sum(valor)                                     as vl_receita,
    count(*)                                       as qt_lancamentos,

    -- Quantas ORIGENS distintas de dinheiro, nao quantos lancamentos. Cinquenta
    -- doacoes da mesma pessoa sao um doador, e a diferenca importa.
    count(distinct sk_doador)                      as qt_doadores,
    countif(doador_tipo = 'fisica')                as qt_lancamentos_pessoa_fisica,
    countif(doador_tipo = 'juridica')              as qt_lancamentos_pessoa_juridica,

    -- Recurso proprio do candidato, isolado: nao e' financiamento de terceiro e
    -- somar com doacao recebida confundiria patrimonio com apoio.
    sum(if(e_autofinanciamento, valor, 0))         as vl_autofinanciamento,

    min(data_receita)                              as dt_primeira_receita,
    max(data_receita)                              as dt_ultima_receita,
    max(_extracted_at)                             as _extracted_at

from receitas
group by sk_candidatura, origem_recurso
