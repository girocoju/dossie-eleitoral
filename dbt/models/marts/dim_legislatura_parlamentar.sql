{{
  config(
    materialized = 'table',
    cluster_by   = ['id_pessoa'],
    description  = 'Em quais legislaturas cada pessoa teve mandato de deputado (ADR-024).'
  )
}}

/*
  Grao: (id_pessoa, casa, id_legislatura).

  POR QUE ISTO EXISTE

  Ter atividade registrada na Camara num ano NAO significa ter sido deputado
  naquele ano. Descoberto em 30/08/2026, na ficha de Ronaldo Caiado: a atividade
  aparecia em 2015-2017, quando ele era SENADOR.

  O dado nao estava errado. As 102 proposicoes sao emendas a Medidas Provisorias
  e um parecer de relator — senador atua na comissao mista de MP, e a Camara
  registra a autoria. Um dos registros diz, com o rotulo defasado da propria
  fonte, "Parecer do Relator, Dep. Ronaldo Caiado (DEM-GO)".

  O ERRO SERIA DO ROTULO, e nao do numero: apresentar aquilo sob "55a legislatura
  da Camara dos Deputados" afirmaria um mandato que nao houve. E' o mesmo tipo de
  erro do "2006 · Nao eleito" — o dado certo, a afirmacao errada.

  Este modelo diz em que legislaturas a pessoa REALMENTE teve mandato, e a ficha
  usa isso para separar as duas coisas em vez de fundi-las.

  A dedupe de `stg_camara__parlamentares` mantem uma linha por PESSOA, para a
  ponte de identidade nao multiplicar quem serviu varias vezes. Aqui e' o oposto:
  quer-se justamente uma linha por legislatura.
*/

with historico as (

    select
        cpf_hash                        as id_pessoa,
        casa,
        -- ja' chega INT64 da ingestao; passar por `limpa` daria TRIM(INT64)
        id_legislatura
    from {{ source('raw_legislativo', 'parlamentares_historico') }}
    where cpf_hash is not null

),

atual as (

    -- Quem esta' em exercicio hoje: 57a legislatura. A tabela diaria nao carrega
    -- a coluna nos registros antigos, entao o valor e' fixado aqui.
    select
        p.id_pessoa,
        p.casa,
        57 as id_legislatura
    from {{ ref('dim_parlamentar') }} p
    -- `em_exercicio` e' indispensavel aqui. Sem ele, TODO ex-deputado da ponte
    -- historica entraria como parlamentar da 57a legislatura — e a ficha de
    -- Ronaldo Caiado, governador de Goias, dizia que ele tem mandato de deputado
    -- agora. O dado da ponte estava certo; a atribuicao e' que era falsa.
    where p.id_pessoa is not null and p.em_exercicio

)

select distinct
    id_pessoa,
    casa,
    id_legislatura,
    -- A 52a comeca em 2003 e cada legislatura dura quatro anos. A aritmetica e'
    -- exata para todo o periodo que o projeto cobre, e evita uma tabela de
    -- dominio que precisaria ser mantida a mao.
    2003 + 4 * (id_legislatura - 52) as ano_inicio,
    2006 + 4 * (id_legislatura - 52) as ano_fim
from (
    select * from historico
    union all
    select * from atual
)
where id_legislatura is not null
