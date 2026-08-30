{{
  config(
    materialized = 'table',
    cluster_by   = ['id_pessoa', 'ano'],
    description  = 'Votos e presenca de deputado, por ano (F-20, ADR-025).'
  )
}}

/*
  Grao: (id_deputado, ano).

  Duas medidas de presenca no trabalho legislativo que as proposicoes nao contam:
  quantas vezes a pessoa VOTOU, e em quantos eventos ESTEVE.

  NAO EXISTE TAXA DE PRESENCA AQUI, E ISSO E' DELIBERADO

  A fonte diz em que eventos o deputado esteve. NAO diz a quantos ele DEVIA ter
  comparecido — e sem denominador nao existe percentual. Derivar um exigiria
  decidir o que conta como ausencia, e falta se confunde com comissao paralela,
  missao oficial e licenca medica.

  Um "62% de presenca" errado e' uma acusacao publicada sobre uma pessoa real. A
  frequencia oficial existe no portal da Camara, fora do dado aberto: o caminho
  honesto seria cita-la, nao inferi-la.

  Fica o VOLUME, que e' fato verificavel. Comparar dois deputados por ele exige
  saber que os mandatos tem duracoes diferentes, e a tela diz isso.

  PLENARIO SEPARADO DE COMISSAO

  Sessao de plenario e reuniao de comissao sao trabalhos diferentes. Somar os
  dois num numero so' esconderia a diferenca; a coluna separada deixa visivel.

  O QUE NAO SE FAZ COM O VOTO

  A distribuicao (sim, nao, abstencao, obstrucao) esta' aqui porque e' registro
  publico. O que o projeto NAO faz e' interpreta-la: um voto so' significa algo
  junto com o que estava em votacao, e classificar isso seria editorializar
  (Constituicao 0.1). A tela mostra os numeros e nao conclui nada deles.
*/

with votos as (

    select
        id_deputado, ano, id_legislatura,
        nome_deputado, sigla_partido, sg_uf,
        qt_votacoes, qt_sim, qt_nao, qt_abstencao, qt_obstrucao,
        qt_artigo_17, qt_outro, _extracted_at
    from {{ source('raw_legislativo', 'votos_deputado') }}

),

presenca as (

    select id_deputado, ano, qt_eventos, qt_eventos_plenario
    from {{ source('raw_legislativo', 'presenca_deputado') }}

),

parlamentares as (

    select id_casa, id_pessoa, casamento_confiavel
    from {{ ref('dim_parlamentar') }}
    where casa = 'camara'

),

juntos as (

    -- FULL JOIN: ha' deputado que votou num ano sem constar da presenca e
    -- vice-versa. Usar INNER perderia linhas legitimas em silencio.
    select
        coalesce(v.id_deputado, p.id_deputado)              as id_deputado,
        coalesce(v.ano, p.ano)                              as ano,
        v.id_legislatura, v.nome_deputado, v.sigla_partido, v.sg_uf,
        v.qt_votacoes, v.qt_sim, v.qt_nao, v.qt_abstencao,
        v.qt_obstrucao, v.qt_artigo_17, v.qt_outro,
        p.qt_eventos, p.qt_eventos_plenario,
        v._extracted_at
    from votos v
    full join presenca p
      on v.id_deputado = p.id_deputado and v.ano = p.ano

)

select
    j.id_deputado,
    j.ano,
    -- A legislatura sai da aritmetica quando a fonte de votos nao cobre o ano
    -- (deputado que so' aparece na presenca).
    coalesce({{ inteiro('j.id_legislatura') }}, 52 + div(j.ano - 2003, 4)) as id_legislatura,
    j.nome_deputado,
    j.sigla_partido,
    j.sg_uf,

    coalesce(j.qt_votacoes, 0)            as qt_votacoes,
    coalesce(j.qt_sim, 0)                 as qt_sim,
    coalesce(j.qt_nao, 0)                 as qt_nao,
    coalesce(j.qt_abstencao, 0)           as qt_abstencao,
    coalesce(j.qt_obstrucao, 0)           as qt_obstrucao,
    coalesce(j.qt_artigo_17, 0)           as qt_artigo_17,
    coalesce(j.qt_outro, 0)               as qt_outro,

    -- NULL, e nao zero: a fonte de presenca pode nao cobrir o ano, e "nao sei"
    -- nao e' "nao compareceu". E' a mesma regra do resultado eleitoral (ADR-023).
    j.qt_eventos,
    j.qt_eventos_plenario,

    p.id_pessoa,
    p.id_pessoa is not null               as ligado_ao_tse,
    coalesce(p.casamento_confiavel, false) as casamento_confiavel,
    j._extracted_at

from juntos j
left join parlamentares p on j.id_deputado = p.id_casa
