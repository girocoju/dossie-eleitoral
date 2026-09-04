{{
  config(
    materialized = 'table',
    cluster_by   = ['id_pessoa', 'ano_emenda'],
    description  = 'Emendas por autor e ano, so\' com autor identificado (F-27).'
  )
}}

/*
  Grao: (id_pessoa, ano_emenda, tipo).

  ── UMA LINHA POR ANO. NUNCA UM TOTAL DE CARREIRA. ──

  O Portal publica um arquivo cumulativo: 94.463 linhas, emendas de 2014 a 2026,
  com o valor ja' acumulado de empenho e pagamento.

  Somar todos os anos numa linha so' produziria um numero grande e sem
  significado — "moveu R$ 300 milhoes" sem dizer em quantos anos, num mandato ou
  em quatro. O ano e' a unica coisa que da' escala a' cifra, e por isso ele fica
  na chave e nao ha' total.

  ── O CASAMENTO E' POR NOME, E NOME AMBIGUO NAO ENTRA ──

  O Portal publica o nome do autor no formato de `nome_parlamentar` e um codigo
  proprio, sem relacao com CPF nem com o id da Camara. O casamento e' por nome
  normalizado.

  Medido em 04/09/2026 sobre os 1.544 autores individuais de 2025:

      nome unico            1.302 autores ·  68.366 linhas   (93%)
      nome AMBIGUO              7 autores ·     369 linhas   ( 0%)
      sem correspondencia     235 autores ·   5.121 linhas

  Os sete ambiguos sao homonimia de verdade: RICARDO IZAR (pai e filho, os dois
  deputados), ATILA LIRA, JOAO CARLOS BACELAR, BEBETO. Atribuir milhoes de reais
  a' pessoa errada e' o pior erro possivel nesta tela — nome que resolve para
  mais de uma pessoa NAO entra.

  A chave `nome -> uma pessoa so'` e' checada aqui dentro, contra
  `dim_parlamentar` inteira; nao basta o nome ser unico na Camara.

  ── O QUE NAO ENTRA ──

  Autor coletivo (RELATOR GERAL, bancada, comissao) e autoria nao publicada —
  17% do arquivo. Nao sao dado faltando por descuido: sao 15.962 linhas que o
  proprio Portal publica sem autor (L-29). Ficam em
  `stg_transparencia__emendas`, e a tela DIZ que existem, porque um bloco que
  nao diga isso sugere que a lista esta' completa.
*/

with execucao as (

    select *
    from {{ ref('stg_transparencia__emendas') }}
    where autor_e_pessoa
      and autor_normalizado is not null

),

-- Nome que resolve para mais de uma pessoa fica de fora. O CTE existe separado
-- para que a exclusao seja legivel, e nao um `having` escondido no fim.
nomes as (

    select
        {{ sem_acento('nome_parlamentar') }}            as nome_normalizado,
        count(distinct id_pessoa)                       as qt_pessoas,
        any_value(id_pessoa)                            as id_pessoa
    from {{ ref('dim_parlamentar') }}
    where id_pessoa is not null
    group by 1

),

com_pessoa as (

    select e.*, n.id_pessoa
    from execucao as e
    join nomes as n on n.nome_normalizado = e.autor_normalizado
    where n.qt_pessoas = 1

)

select
    id_pessoa,
    ano_emenda,
    tipo,

    count(*)                                            as qt_linhas,
    count(distinct codigo)                              as qt_emendas,
    count(distinct cod_municipio)                       as qt_municipios,
    count(distinct sg_uf)                               as qt_ufs,

    sum(vl_empenhado)                                   as vl_empenhado,
    sum(vl_liquidado)                                   as vl_liquidado,
    sum(vl_pago)                                        as vl_pago,
    sum(vl_restos_pagos)                                as vl_restos_pagos,

    -- A funcao com mais dinheiro pago no ano. Nao e' ranking de politico:
    -- e' para que a linha diga PARA ONDE o recurso foi, e nao so' quanto.
    array_agg(funcao order by vl_pago desc limit 1)[safe_offset(0)] as funcao_principal,

    max(_extracted_at)                                  as _extracted_at

from com_pessoa
group by id_pessoa, ano_emenda, tipo
