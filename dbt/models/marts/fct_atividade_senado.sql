{{
  config(
    materialized = 'table',
    cluster_by   = ['id_casa', 'classe_proposicao'],
    description  = 'Atividade legislativa por senador, ano e classe de proposicao (F-22). Fecha a L-20.'
  )
}}

/*
  Grao: (id_casa, ano, classe_proposicao). Espelha `fct_atividade_legislativa`.

  ── SO' AUTORIA PRINCIPAL ──

  Entram apenas as linhas com `autor_principal` — `ordem_assinatura = 1`, o
  equivalente do `proponente = 1` da Camara. Era exatamente isto que a L-20
  exigia antes de deixar o Senado entrar: sem esse filtro, um senador com 200
  assinaturas de apoio apareceria ao lado de um deputado com 200 projetos
  proprios, na mesma coluna e com o mesmo rotulo.

  ── A CLASSE FAZ PARTE DA CHAVE, E NAO EXISTE LINHA "TOTAL" ──

  Mesma decisao do modelo da Camara, pelo mesmo motivo: somar as classes produz o
  numero que circula na imprensa e nao significa nada. Numa amostra de quatro
  senadores havia 1.445 requerimentos para 242 projetos de lei — quem soma
  compara volume de rito com producao normativa.

  O mapeamento das siglas saiu da lista OFICIAL do Senado, e nao do formato da
  sigla: `RQI` parece "Requerimento de Informacao" e e' "Requerimento da Comissao
  de Servicos de Infraestrutura". Ver `ingest/senado.py`.

  ── O QUE ESTE MODELO NAO TEM ──

  Taxa de aprovacao, pelo mesmo motivo da Camara: aprovar depende de estar na
  base do governo, nao do merito do texto (Constituicao 0.1).

  E nao tem comparacao entre as casas. Deputado e senador nao propoem as mesmas
  coisas nem no mesmo volume; os dois blocos existem lado a lado na ficha, nunca
  somados nem postos em placar.
*/

with autorias as (

    select *
    from {{ ref('stg_senado__autoria') }}
    where autor_principal

),

ponte as (

    -- So' o Senado: `id_casa` aqui e' o `codigoParlamentar` da API do Senado, que
    -- nao tem relacao com o `id_deputado` da Camara.
    select
        -- `id_casa` viaja como STRING em `dim_parlamentar` (a Camara publica com
        -- zeros a' esquerda em alguns endpoints) e como INT64 aqui, que e' o tipo
        -- do `codigoParlamentar` da API do Senado. O cast fica de um lado so',
        -- explicito, em vez de mudar o tipo da dimensao que outros modelos usam.
        safe_cast(id_casa as int64)                         as id_casa,
        id_pessoa,
        metodo_id_pessoa,
        casamento_confiavel,
        nome_parlamentar,
        url_perfil
    from {{ ref('dim_parlamentar') }}
    where casa = 'senado'

),

agregado as (

    select
        id_casa,
        ano,
        classe_proposicao,
        any_value(nome_autor)                               as nome_autor,
        any_value(sigla_partido_autor)                      as sigla_partido_autor,
        any_value(sigla_uf_autor)                           as sigla_uf_autor,
        count(*)                                            as qt_proposicoes,
        countif(tramitando = 'Sim')                         as qt_em_tramitacao,
        count(distinct sigla)                               as qt_tipos_distintos,
        min(data_apresentacao)                              as primeira_apresentacao,
        max(data_apresentacao)                              as ultima_apresentacao,
        max(_extracted_at)                                  as _extracted_at
    from autorias
    group by id_casa, ano, classe_proposicao

)

select
    a.id_casa,
    a.ano,
    a.classe_proposicao,
    a.nome_autor,
    a.sigla_partido_autor,
    a.sigla_uf_autor,
    a.qt_proposicoes,
    a.qt_em_tramitacao,
    a.qt_tipos_distintos,
    a.primeira_apresentacao,
    a.ultima_apresentacao,

    p.id_pessoa,
    p.id_pessoa is not null                                 as ligado_ao_tse,
    p.casamento_confiavel,
    p.metodo_id_pessoa,
    p.nome_parlamentar,
    p.url_perfil,

    a._extracted_at

from agregado as a
left join ponte as p using (id_casa)
