{{
  config(
    materialized = 'table',
    cluster_by   = ['casa', 'sg_uf'],
    description  = 'Parlamentar em exercicio resolvido contra o cadastro do TSE (F-15).'
  )
}}

/*
  Grao: (casa, id_casa) — um deputado ou senador em exercicio.

  Resolve a identidade em duas tentativas, nesta ordem:

    1. `cpf_hash`             — exato. E' a mesma chave que liga eleicoes entre si.
    2. `chave_nome_nascimento` — inferido. Nome sem acento + data de nascimento.

  A ordem importa: o CPF e' afirmacao da fonte, o nome e' deducao nossa. A segunda
  tentativa so' vale quando a primeira nao tem material — e o resultado carrega
  `metodo_id_pessoa` para que a tela saiba qual das duas usou.

  AMBIGUIDADE NAO VIRA CASAMENTO. Se duas pessoas diferentes no TSE compartilham
  nome e data de nascimento, `id_pessoa` fica NULL e `id_ambiguo = true`. Atribuir
  o mandato de um homonimo a outro seria pior do que nao mostrar nada: o painel
  colaria a ficha de uma pessoa no rosto de outra.
*/

with parlamentares as (

    select * from {{ ref('stg_camara__parlamentares') }}

),

candidatos as (

    select distinct id_pessoa, cpf_hash, chave_nome_nascimento
    from {{ ref('dim_candidato') }}
    where id_pessoa is not null

),

-- Tentativa 1: CPF. Um cpf_hash so' pode apontar para uma pessoa, entao aqui nao
-- ha' ambiguidade possivel.
por_cpf as (

    select distinct cpf_hash, id_pessoa
    from candidatos
    where cpf_hash is not null

),

-- Tentativa 2: nome + nascimento. Aqui ha': guardamos quantas pessoas distintas
-- respondem pela mesma chave para poder recusar as duvidosas.
por_nome as (

    select
        chave_nome_nascimento,
        any_value(id_pessoa)        as id_pessoa,
        count(distinct id_pessoa)   as pessoas_distintas
    from candidatos
    where chave_nome_nascimento is not null
    group by chave_nome_nascimento

)

select
    p.casa,
    p.id_casa,
    p.nome_parlamentar,
    p.nome_completo,
    p.data_nascimento,
    p.sexo,
    p.sigla_partido,
    p.sg_uf,
    p.url_perfil,

    case
        when c.id_pessoa is not null then c.id_pessoa
        when n.id_pessoa is not null and n.pessoas_distintas = 1 then n.id_pessoa
    end                                                         as id_pessoa,

    case
        when c.id_pessoa is not null then 'cpf'
        when n.id_pessoa is not null and n.pessoas_distintas = 1 then 'nome_nascimento'
        when n.pessoas_distintas > 1 then 'ambiguo'
        else 'sem_correspondencia'
    end                                                         as metodo_id_pessoa,

    -- TRUE so' pelo CPF. O casamento por nome funciona e cobre o Senado inteiro,
    -- mas continua sendo deducao, e a tela precisa poder dizer isso.
    c.id_pessoa is not null                                     as casamento_confiavel,
    /*
      Ambiguidade que EFETIVAMENTE impede a resolucao — e nao qualquer homonimia.

      Seis deputados tem homonimo com a mesma data de nascimento no cadastro do
      TSE e mesmo assim foram resolvidos pelo CPF, sem duvida nenhuma. Marca-los
      como ambiguos poluiria a tela com um alerta que nao corresponde a risco
      algum, e alerta que aparece sem motivo e' alerta que para de ser lido.
    */
    (c.id_pessoa is null and coalesce(n.pessoas_distintas, 0) > 1) as id_ambiguo,

    p._extracted_at
from parlamentares as p
left join por_cpf  as c on p.cpf_hash = c.cpf_hash
left join por_nome as n on p.chave_nome_nascimento = n.chave_nome_nascimento
