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

  ── O PAPEL AQUI E' MAIS POBRE QUE O DA CAMARA, E DE PROPOSITO ──

  A rota do Senado devolve apenas Titular, Suplente e Nato. Nao ha' Presidente
  nem Relator, entao a ficha de senador NAO afirma quem presidiu um colegiado —
  ao contrario da de deputado. E' ausencia da fonte, nao escolha nossa, e a
  alternativa (deduzir presidencia de outra rota) inventaria o dado (Regra 5).
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
        case
            when {{ sem_acento('papel') }} like 'TITULAR%'  then 1
            when {{ sem_acento('papel') }} like 'NATO%'     then 2
            when {{ sem_acento('papel') }} like 'SUPLENTE%' then 3
            else 4
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

    array_agg(papel order by peso_papel limit 1)[offset(0)] as papel_principal,
    count(distinct papel)                               as qt_papeis,

    min(data_inicio)                                    as primeiro_inicio,
    max(coalesce(data_fim, data_inicio))                as ultimo_fim,
    logical_or(em_curso)                                as em_curso,
    count(*)                                            as qt_periodos,

    max(_extracted_at)                                  as _extracted_at

from pesado
group by id_pessoa, codigo_colegiado
