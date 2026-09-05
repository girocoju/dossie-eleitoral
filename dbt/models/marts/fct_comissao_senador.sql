{{
  config(
    materialized = 'table',
    cluster_by   = ['id_pessoa', 'classe_colegiado'],
    description  = 'Onde cada senador sentou, com que papel e por quanto tempo (F-29). Fecha a L-28.'
  )
}}

/*
  Grao: (id_pessoa, codigo_colegiado) — um colegiado por linha, ja' com os
  periodos somados. Espelha `fct_comissao_deputado`.

  ── A IDENTIDADE E' INFERIDA, E A TELA PRECISA DIZER ISSO ──

  Aqui esta' a diferenca que mais importa em relacao a' Camara. La', o filtro e'
  `casamento_confiavel` — casamento por CPF (ADR-014). O Senado NAO publica CPF,
  entao nenhum senador tem casamento confiavel, e exigi-lo aqui zeraria o modelo.

  O filtro e' `id_pessoa is not null`: ligacao por `chave_nome_nascimento`, o
  mesmo criterio que `fct_atividade_senado` ja' usa em producao desde a F-22
  (ADR-034). Nao e' um padrao mais frouxo inventado para esta feature — e' o
  padrao do Senado no projeto, e ele viaja com a ressalva na tela.

  `casamento_confiavel` e `metodo_id_pessoa` seguem ate' o fim para que quem
  renderiza possa dizer ao leitor como a pessoa foi identificada.

  ── O QUE ENTRA COMO COLEGIADO ──

  As mesmas cinco classes da Camara. `frente` e `grupo_amizade` ficam de fora
  pelo mesmo motivo de la': sao adesao aberta, nao assento — 1.497 vinculos que
  diriam pouco sobre o mandato e empurrariam a comissao permanente para baixo na
  ficha. Continuam gravados em `stg_senado__comissoes`.

  `desconhecida` fica de fora por outro motivo: nao sabemos o que e'. Ver a
  secao seguinte.

  ── O PAPEL VEM DE DUAS ROTAS, E ISSO MUDA A CONTAGEM ──

  `/comissoes` devolve quem SENTOU (Titular, Suplente, Nato) e `/cargos` devolve
  quem COMANDOU (Presidente, Vice, Relator, Secretario). A ingestao une as duas,
  e `origem_do_vinculo` distingue.

  A consequencia esta' nas contagens: `qt_periodos` conta apenas DESIGNACOES —
  somar as linhas de cargo faria "designado 4 vezes" onde houve duas designacoes
  e duas presidencias. O comando tem contador proprio, `qt_cargos`.

  Colegiado que so' aparece em `/cargos` — a Mesa Diretora e' o caso — fica com
  `qt_periodos = 0`. Nao e' buraco: e' a fonte publicando o cargo sem publicar a
  designacao, e a tela diz isso em vez de inventar um numero (Regra 5).

  ── O PAPEL DE AGORA NAO E' O PAPEL DE MAIOR PESO DE SEMPRE ──

  Sao DOIS campos, e confundi-los publica uma afirmacao falsa sobre gente real.

  `em_curso` e' verdadeiro quando ALGUM periodo esta' aberto. Um senador que
  preside a CDH em 2015 e segue titular dela hoje tem os dois: presidencia
  encerrada, titularidade aberta. Um unico `papel_principal` combinado com
  `em_curso` diria "Presidente da CDH, em curso" — e a CDH apareceria com CINCO
  presidentes simultaneos, que foi o que a primeira versao deste modelo produziu.

      papel_atual       o de maior peso entre os periodos ABERTOS; nulo se
                        nenhum esta' aberto
      papel_principal   o de maior peso de toda a trajetoria ali

  A tela mostra `papel_atual` ao lado de "em curso" e guarda `papel_principal`
  para a linha historica. Conferido: presidencia em curso e' UMA por colegiado,
  nas 19 comissoes permanentes e na Mesa.
*/

with assentos as (

    select *
    from {{ ref('stg_senado__comissoes') }}
    where classe_colegiado in ('mesa', 'permanente', 'temporaria', 'conselho', 'mista')

),

ponte as (

    -- `id_casa` viaja como STRING em `dim_parlamentar` e como INT64 aqui, que e'
    -- o tipo do `codigoParlamentar` da API do Senado. Mesmo cast de um lado so'
    -- que `fct_atividade_senado` faz.
    select
        safe_cast(id_casa as int64)                     as codigo_parlamentar,
        id_pessoa,
        metodo_id_pessoa,
        casamento_confiavel,
        nome_parlamentar
    from {{ ref('dim_parlamentar') }}
    where casa = 'senado'
      and id_pessoa is not null

),

com_pessoa as (

    select a.*, p.id_pessoa, p.metodo_id_pessoa, p.casamento_confiavel
    from assentos as a
    join ponte as p using (codigo_parlamentar)

),

pesado as (

    select
        *,
        -- Hierarquia FORMAL do colegiado, nao merito. Numero menor = mais peso.
        --
        -- A fonte escreve o ordinal junto ("1o VICE-PRESIDENTE", "2a
        -- SECRETARIA"), entao o teste e' por CONTEUDO e nao por prefixo. E o
        -- vice e' testado antes do presidente: "VICE-PRESIDENTE" contem
        -- "PRESIDENTE", e a ordem inversa promoveria todo vice a presidente.
        case
            when {{ sem_acento('papel') }} like '%VICE-PRESIDENTE%' then 2
            when {{ sem_acento('papel') }} like '%PRESIDENTE%'      then 1
            when {{ sem_acento('papel') }} like '%SECRETARI%'       then 3
            when {{ sem_acento('papel') }} like '%CORREGEDOR%'      then 3
            when {{ sem_acento('papel') }} like '%OUVIDOR%'         then 3
            when {{ sem_acento('papel') }} like '%RELATOR%'         then 4
            when {{ sem_acento('papel') }} like '%COORDENADOR%'     then 5
            when {{ sem_acento('papel') }} like 'TITULAR%'          then 6
            when {{ sem_acento('papel') }} like 'NATO%'             then 7
            when {{ sem_acento('papel') }} like '%SUPLENTE%'        then 8
            else 9
        end                                             as peso_papel
    from com_pessoa

)

select
    id_pessoa,
    codigo_colegiado,
    any_value(classe_colegiado)                         as classe_colegiado,
    any_value(tipo_colegiado)                           as tipo_colegiado,
    any_value(sigla_colegiado)                          as sigla_colegiado,
    any_value(nome_colegiado)                           as nome_colegiado,
    any_value(casa_colegiado)                           as casa_colegiado,

    -- Como o tipo daquele colegiado foi determinado: `catalogo` (veio da fonte)
    -- ou `nome` (deduzido da forma oficial por extenso). Ver ADR-048.
    any_value(origem_da_classe)                         as origem_da_classe,

    -- Como a pessoa foi identificada. O Senado nao publica CPF, entao isto e'
    -- sempre casamento por nome + nascimento, e a tela diz.
    any_value(metodo_id_pessoa)                         as metodo_id_pessoa,
    logical_or(casamento_confiavel)                     as casamento_confiavel,

    -- O de maior peso de toda a trajetoria ali.
    array_agg(papel order by peso_papel limit 1)[offset(0)] as papel_principal,

    -- O de maior peso entre os periodos ABERTOS. Nulo quando nenhum esta'
    -- aberto — e e' esse nulo que impede a tela de dizer "Presidente, em curso"
    -- de quem presidiu ha' dez anos e hoje so' e' titular.
    array_agg(if(em_curso, papel, null) ignore nulls
              order by peso_papel limit 1)[safe_offset(0)] as papel_atual,
    min(if(em_curso, peso_papel, null))                 as peso_atual,

    count(distinct papel)                               as qt_papeis,

    -- Conta DESIGNACAO, nao cargo: as duas rotas descrevem o mesmo periodo por
    -- angulos diferentes, e somar produziria o dobro.
    countif(origem_do_vinculo = 'comissoes')            as qt_periodos,
    countif(origem_do_vinculo = 'cargos')               as qt_cargos,
    logical_or(peso_papel <= 5)                         as teve_comando,
    logical_or(em_curso and peso_papel <= 5)            as comanda_agora,

    min(data_inicio)                                    as primeiro_inicio,
    max(coalesce(data_fim, data_inicio))                as ultimo_fim,
    logical_or(em_curso)                                as em_curso,

    max(_extracted_at)                                  as _extracted_at

from pesado
group by id_pessoa, codigo_colegiado
