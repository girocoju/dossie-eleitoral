{{
  config(
    materialized = 'table',
    cluster_by   = ['id_pessoa', 'classe_orgao'],
    description  = 'Onde cada deputado sentou, com que papel e por quanto tempo (F-26).'
  )
}}

/*
  Grao: (id_pessoa, id_orgao, classe_orgao) — um colegiado por linha, ja' com os
  periodos somados.

  ── POR QUE SOMAR OS PERIODOS ──

  A Camara renova a composicao das comissoes todo ano, e o mesmo deputado
  reaparece na mesma comissao a cada renovacao. Medido em 04/09/2026: 25
  deputados produziram 490 assentos em comissao permanente — cerca de vinte cada
  um, quase todos repetindo o mesmo colegiado.

  Listar as 490 linhas na ficha seria enterrar a informacao no proprio volume.
  Somadas por orgao, viram "CCJC — Titular, 2007 a 2015", que e' o que alguem
  quer saber.

  ── O PAPEL DE MAIOR PESO PREVALECE, E ISSO NAO E' RANKING ──

  Quem foi Presidente da comissao num ano e Suplente noutro aparece como
  Presidente, com a nota do periodo. Nao e' juizo sobre a pessoa: e' escolher,
  entre fatos igualmente verdadeiros, o mais informativo — do mesmo jeito que a
  trajetoria mostra o resultado do turno decisivo e nao a soma dos turnos.

  A ordem e' a hierarquia FORMAL do colegiado, nao merito:
  Presidente > Vice-Presidente > Relator > Titular > Suplente.

  ── O QUE NAO ENTRA ──

  `partidaria` (partido, bloco, lideranca, bancada) e `medida_provisoria` ficam
  de fora da promocao a colegiado. A primeira porque estar no PT nao e' ter
  assento na CCJ; a segunda porque sao 1.393 comissoes de MPV no catalogo e
  participar delas e' rotina — a ficha conta quantas, sem enumerar.

  Nada disso e' apagado: as linhas continuam em `stg_camara__comissoes`.

  ── SO' QUEM TEM IDENTIDADE CONFIRMADA ──

  `casamento_confiavel` e' o filtro. Na Camara ele significa casamento por CPF
  (ADR-014), e sem ele um assento na CCJ poderia ser atribuido a um homonimo —
  uma afirmacao falsa publicada sobre uma pessoa real.
*/

with assentos as (

    select *
    from {{ ref('stg_camara__comissoes') }}
    where classe_orgao in ('mesa', 'permanente', 'temporaria', 'conselho', 'mista')

),

ponte as (

    select
        safe_cast(id_casa as int64)                     as id_deputado,
        id_pessoa,
        nome_parlamentar
    from {{ ref('dim_parlamentar') }}
    where casa = 'camara'
      and casamento_confiavel
      and id_pessoa is not null

),

com_pessoa as (

    select a.*, p.id_pessoa
    from assentos as a
    join ponte as p using (id_deputado)

),

pesado as (

    select
        *,
        -- Hierarquia FORMAL do colegiado. Numero menor = papel de maior peso.
        case
            when {{ sem_acento('papel') }} like 'PRESIDENTE%'      then 1
            when {{ sem_acento('papel') }} like '%VICE-PRESIDENTE%' then 2
            when {{ sem_acento('papel') }} like 'RELATOR%'          then 3
            when {{ sem_acento('papel') }} like 'TITULAR%'          then 4
            when {{ sem_acento('papel') }} like 'SUPLENTE%'         then 5
            else 6
        end                                             as peso_papel
    from com_pessoa

)

select
    id_pessoa,
    id_orgao,
    any_value(classe_orgao)                             as classe_orgao,
    any_value(tipo_orgao)                               as tipo_orgao,
    any_value(sigla_orgao)                              as sigla_orgao,
    any_value(nome_orgao)                               as nome_orgao,

    -- O papel de maior peso, e quantos papeis diferentes a pessoa teve ali.
    array_agg(papel order by peso_papel limit 1)[offset(0)] as papel_principal,
    count(distinct papel)                               as qt_papeis,

    min(data_inicio)                                    as primeiro_inicio,
    max(coalesce(data_fim, data_inicio))                as ultimo_fim,
    logical_or(em_curso)                                as em_curso,
    count(*)                                            as qt_periodos,

    max(_extracted_at)                                  as _extracted_at

from pesado
group by id_pessoa, id_orgao
