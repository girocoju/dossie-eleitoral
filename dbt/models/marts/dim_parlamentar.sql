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

  ── MAS REGISTRO SEM CPF NAO E' PROVA DE UMA SEGUNDA PESSOA ──

  `id_pessoa` e' o `cpf_hash` quando o ano publica CPF e a chave de nome quando
  nao publica (ADR-005). A mesma pessoa fica, entao, com DOIS `id_pessoa` quando
  tem candidatura dos dois lados dessa fronteira — e contar ids distintos leria
  isso como homonimia.

  Medido em 05/09/2026 sobre 131.567 chaves: 326 respondem por mais de um
  `id_pessoa`, e delas

      210   um id por CPF + um pelo fallback     <- fronteira, nao homonimia
      116   dois ou mais ids por CPF             <- homonimia de verdade

  Das 210, **204 nao tem um unico ano em comum** entre os dois ids e 183
  concorreram sempre na mesma UF. E' a marca de um registro antigo sem CPF, nao
  de duas pessoas.

  A contagem que decide a ambiguidade passa a ser a de identidades COM CPF. Isto
  nao funde ninguem: o `id_pessoa` de cada candidatura continua o que era, e o
  registro sem CPF segue com o dono que tinha. O que muda e' so' a leitura —
  ausencia de CPF deixa de ser tratada como evidencia de outra pessoa.

  Fecha a L-31 (ADR-050). O caso concreto: a presidencia da Comissao de
  Agricultura do Senado, que existia e nao podia ser exibida.
*/

with parlamentares as (

    select * from {{ ref('stg_camara__parlamentares') }}

),

candidatos as (

    select distinct
        id_pessoa,
        cpf_hash,
        chave_nome_nascimento,
        cpf_hash is not null                as tem_cpf
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

/*
  Tentativa 2: nome + nascimento.

  As identidades sao contadas SEPARADAS por procedencia, e nao no mesmo balde:

    com_cpf   `id_pessoa` veio do cpf_hash — afirmacao da fonte
    sem_cpf   `id_pessoa` e' a propria chave de nome — o ano nao publicou CPF

  Duas identidades COM CPF na mesma chave sao duas pessoas, e a chave e'
  recusada. Uma com CPF e uma sem sao a fronteira descrita no cabecalho, e a
  resolucao fica com a que tem CPF: um registro que nao traz CPF nao afirma nada
  sobre existir outra pessoa.

  `any_value` ignora NULL em BigQuery, entao os dois `any_value(if(...))` devolvem
  a identidade daquela procedencia — ou NULL quando nao ha' nenhuma.
*/
por_nome as (

    select
        chave_nome_nascimento,
        count(distinct if(tem_cpf, id_pessoa, null))    as ids_com_cpf,
        count(distinct if(tem_cpf, null, id_pessoa))    as ids_sem_cpf,
        any_value(if(tem_cpf, id_pessoa, null))         as id_com_cpf,
        any_value(if(tem_cpf, null, id_pessoa))         as id_sem_cpf
    from candidatos
    where chave_nome_nascimento is not null
    group by chave_nome_nascimento

),

-- Resolve a chave a uma identidade so', ou a nenhuma.
nome_resolvido as (

    select
        chave_nome_nascimento,
        case
            when ids_com_cpf = 1 then id_com_cpf
            when ids_com_cpf = 0 and ids_sem_cpf = 1 then id_sem_cpf
        end                                             as id_pessoa,
        -- Ambigua de verdade: duas identidades COM CPF, ou — quando nenhuma tem
        -- CPF — duas chaves de nome distintas, que nao deveria acontecer e por
        -- isso tambem e' recusada.
        (ids_com_cpf > 1 or (ids_com_cpf = 0 and ids_sem_cpf > 1)) as ambigua,
        -- A chave tinha os dois lados da fronteira do CPF. Nao muda a resolucao;
        -- existe para que a medicao do cabecalho possa ser refeita.
        (ids_com_cpf = 1 and ids_sem_cpf >= 1)          as chave_partida
    from por_nome

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

    coalesce(c.id_pessoa, n.id_pessoa)                          as id_pessoa,

    case
        when c.id_pessoa is not null then 'cpf'
        when n.id_pessoa is not null then 'nome_nascimento'
        when n.ambigua then 'ambiguo'
        else 'sem_correspondencia'
    end                                                         as metodo_id_pessoa,

    -- A chave respondia por uma identidade com CPF e outra sem, e a resolucao
    -- ficou com a primeira. Nao e' ressalva para a tela: e' rastro para conferir.
    coalesce(n.chave_partida, false)                            as chave_partida,

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
    (c.id_pessoa is null and coalesce(n.ambigua, false))        as id_ambiguo,

    -- Distingue quem esta NO MANDATO de quem apenas ja esteve. A ponte agora
    -- inclui legislaturas encerradas (ADR-024), e sem esta marca todo ex-deputado
    -- seria tratado como parlamentar de hoje.
    p.em_exercicio,
    p._extracted_at
from parlamentares as p
left join por_cpf  as c on p.cpf_hash = c.cpf_hash
left join nome_resolvido as n on p.chave_nome_nascimento = n.chave_nome_nascimento
