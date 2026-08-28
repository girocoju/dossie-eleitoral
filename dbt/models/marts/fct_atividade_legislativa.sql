{{
  config(
    materialized = 'table',
    cluster_by   = ['id_deputado', 'classe_proposicao'],
    description  = 'Atividade legislativa por deputado, ano e classe de proposicao (F-16).'
  )
}}

/*
  Grao: (id_deputado, ano, classe_proposicao).

  A CLASSE FAZ PARTE DA CHAVE, e isso e' a decisao central deste modelo. Nao existe
  linha "total do deputado", de proposito. Somar as classes produziria o numero que
  circula na imprensa e que nao significa nada: em 2025, 7.695 projetos de lei
  conviveram com 31.479 requerimentos de retirada de pauta e 15.501 pareceres de
  relator. Um deputado com 400 requerimentos e outro com 12 projetos de lei
  apareceriam como 400 contra 12.

  O que cada classe responde:

    normativa      propos criar ou mudar lei          (PL, PEC, PLP, MPV...)
    fiscalizacao   pediu contas ao Executivo          (RIC, PFC, RCP)
    relatoria      analisou a proposta de outro       (PRL, PAR, SBT)
    procedimental  rito, homenagem, emenda, destaque  (REQ, RPD, INC, EMC...)
    outra          tipo raro fora das quatro acima

  `relatoria` merece atencao: NAO e' autoria. O deputado nao propos nada, ele
  relatou o texto de outro. E' trabalho de peso e por isso esta' aqui, mas somar
  com projeto de lei confundiria quem escreveu com quem analisou.

  O QUE ESTE MODELO NAO TEM: taxa de aprovacao. Aprovar depende de estar na base do
  governo, nao do merito do texto — a taxa puniria a oposicao por ser oposicao, em
  qualquer governo, e viraria placar (Constituicao 0.1). Ha' `qt_virou_norma` em
  numero absoluto, ao lado do total, e o leitor tira a propria conclusao.
*/

with proposicoes as (

    select * from {{ ref('stg_camara__proposicoes') }}

),

ponte as (

    -- So' a Camara: `proposicoes` e' fonte da Camara e `id_casa` la' e' o mesmo
    -- `id_deputado` que vem no arquivo de autores.
    select id_casa, id_pessoa, metodo_id_pessoa, casamento_confiavel, nome_parlamentar, url_perfil
    from {{ ref('dim_parlamentar') }}
    where casa = 'camara'

),

agregado as (

    select
        id_deputado,
        ano,
        classe_proposicao,
        any_value(nome_autor)                                   as nome_autor,
        any_value(sigla_partido_autor)                          as sigla_partido_autor,
        any_value(sigla_uf_autor)                               as sigla_uf_autor,
        count(*)                                                as qt_proposicoes,
        countif(virou_norma)                                    as qt_virou_norma,
        countif(arquivada)                                      as qt_arquivada,
        /*
          Mais da metade das proposicoes vem com a situacao em branco na fonte.
          Isso NAO e' "em tramitacao" — e' ausente. Sem esta coluna, a tela
          contaria ausencia de informacao como andamento, e o destino de uma
          proposicao pareceria conhecido quando nao e'.
        */
        countif(not situacao_conhecida)                         as qt_destino_desconhecido,
        countif(situacao_conhecida and not arquivada and not virou_norma)
                                                                as qt_em_tramitacao,
        -- Quantas assinaturas a proposicao tipica desta classe carrega. Separa
        -- quem propoe sozinho de quem propoe em bloco de centenas.
        cast(round(avg(total_assinantes)) as int64)             as media_assinantes,
        min(data_apresentacao)                                  as primeira_apresentacao,
        max(data_apresentacao)                                  as ultima_apresentacao,
        max(_extracted_at)                                      as _extracted_at
    from proposicoes
    group by id_deputado, ano, classe_proposicao

)

select
    a.id_deputado,
    a.ano,
    a.classe_proposicao,
    a.nome_autor,
    coalesce(p.nome_parlamentar, a.nome_autor)                  as nome_parlamentar,
    a.sigla_partido_autor,
    a.sigla_uf_autor,
    a.qt_proposicoes,
    a.qt_virou_norma,
    a.qt_arquivada,
    a.qt_em_tramitacao,
    a.qt_destino_desconhecido,
    a.media_assinantes,
    a.primeira_apresentacao,
    a.ultima_apresentacao,
    p.id_pessoa,
    /*
      NULL quando o deputado nao esta' mais em exercicio: a ponte cobre quem esta'
      la' hoje, e a legislatura 2023-2026 passou por 710 deputados por causa de
      suplencias e licencas. Sem `id_pessoa` a linha continua valida como
      atividade da Camara, mas nao chega a' ficha de um candidato — e e' melhor
      nao chegar do que chegar na ficha errada.
    */
    p.id_pessoa is not null                                     as ligado_ao_tse,
    coalesce(p.casamento_confiavel, false)                      as casamento_confiavel,
    coalesce(p.metodo_id_pessoa, 'fora_de_exercicio')           as metodo_id_pessoa,
    p.url_perfil,
    a._extracted_at
from agregado as a
left join ponte as p
    on a.id_deputado = p.id_casa
