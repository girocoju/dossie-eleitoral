{{
  config(
    materialized = 'table',
    cluster_by   = ['cod_indicador', 'sg_uf'],
    description  = 'Indicador x UF x ano, com o comparador nacional e regional na mesma linha (SPEC 5).'
  )
}}

/*
  Grao: (cod_indicador, sg_uf, ano).

  A regra da Constituicao 0.2 — "sempre ao lado de um comparador" — e' garantida
  AQUI, no dado, e nao no visual: toda linha carrega `valor_brasil` e
  `valor_regiao` do mesmo indicador e ano. Nao existe caminho no Power BI que
  mostre o numero de uma UF sem o comparador disponivel, porque eles vem na
  mesma linha.

  `PIB_PER_CAPITA` e' calculado aqui (SPEC 9: transformacao e' no BigQuery, nunca
  em pandas). Nao ha' variavel de PIB per capita por UF na tabela 5938 do SIDRA —
  conferido em 27/08/2026 —, entao ele nasce de PIB / populacao. O PIB vem em
  R$ mil, dai' o fator 1000.
*/

with observado as (

    select
        cod_indicador,
        sg_uf,
        ano,
        valor,
        unidade,
        fonte,
        n_periodos,
        _extracted_at,
        _source_url
    from {{ ref('stg_indicadores') }}

),

pivo as (

    select
        sg_uf,
        ano,
        max(if(cod_indicador = 'PIB', valor, null))        as pib_mil_reais,
        -- A estimativa (t/6579) e' a serie principal, mas ela pula anos de Censo.
        -- Onde ela falta, entra o dado censitario (t/4709) — e' o que devolve 2022
        -- ao PIB per capita e completa a janela dos governadores eleitos em 2018.
        -- Ver L-12: 2023 continua sem populacao em nenhuma das duas tabelas.
        coalesce(
            max(if(cod_indicador = 'POPULACAO', valor, null)),
            max(if(cod_indicador = 'POPULACAO_CENSO', valor, null))
        )                                                  as populacao,
        max(if(cod_indicador = 'PIB', _extracted_at, null)) as _extracted_at,
        max(if(cod_indicador = 'PIB', _source_url, null))  as _source_url
    from observado
    where cod_indicador in ('PIB', 'POPULACAO', 'POPULACAO_CENSO')
    group by sg_uf, ano

),

derivado as (

    select
        'PIB_PER_CAPITA'                                    as cod_indicador,
        sg_uf,
        ano,
        safe_divide(pib_mil_reais * 1000, populacao)        as valor,
        'R$ correntes por habitante'                        as unidade,
        'Calculado: IBGE t/5938 (PIB) / IBGE t/6579 (populacao)' as fonte,
        1                                                   as n_periodos,
        _extracted_at,
        _source_url
    from pivo
    where pib_mil_reais is not null
      and populacao is not null
      and populacao > 0

),

-- receita e despesa lado a lado, para a subtracao ficar num passo separado da
-- agregacao (o BigQuery recusa agregacao dentro de agregacao)
pivo_orcamento as (

    select
        sg_uf,
        ano,
        max(if(cod_indicador = 'RECEITA_ESTADUAL', valor, null))  as receita,
        max(if(cod_indicador = 'DESPESA_ESTADUAL', valor, null))  as despesa,
        max(_extracted_at)                                        as _extracted_at,
        max(_source_url)                                          as _source_url
    from observado
    where cod_indicador in ('RECEITA_ESTADUAL', 'DESPESA_ESTADUAL')
    group by sg_uf, ano

),

orcamento as (

    /*
      Resultado orcamentario = receita liquida menos despesa empenhada.
      Positivo e' superavit, negativo e' deficit — e nenhum dos dois e' nota de
      gestao: deficit pode ser investimento deliberado, superavit pode ser
      contingenciamento. A tela mostra o numero com comparador, nunca um juizo
      (Constituicao 0.1).
    */
    select
        'RESULTADO_ORCAMENTARIO'                            as cod_indicador,
        sg_uf,
        ano,
        receita - despesa                                   as valor,
        'R$ correntes'                                      as unidade,
        'Calculado: SICONFI receita liquida menos despesa empenhada' as fonte,
        1                                                   as n_periodos,
        _extracted_at,
        _source_url
    from pivo_orcamento
    where receita is not null
      and despesa is not null

),

/*
  O SICONFI publica por ente: 27 estados, sem agregado nacional. Sem um `BR`, a
  regra do comparador obrigatorio (Constituicao 0.2) ficaria sem o lado nacional
  justamente nos indicadores fiscais.

  A soma dos 27 estados E' um agregado legitimo — e' o conjunto das financas
  estaduais —, mas NAO e' "o Brasil" no sentido de orcamento da Uniao. Por isso a
  `fonte` diz explicitamente "soma dos 27 estados": quem ler a linha sabe o que
  esta' vendo.

  So' vale para valores somaveis. Somar taxa de desocupacao ou de homicidios seria
  absurdo, e por isso a lista de indicadores aqui e' fixa.
*/
nacional_somado as (

    select
        cod_indicador,
        'BR'                                                as sg_uf,
        ano,
        sum(valor)                                          as valor,
        any_value(unidade)                                  as unidade,
        'Tesouro Nacional — SICONFI/DCA (soma dos 27 estados)' as fonte,
        1                                                   as n_periodos,
        max(_extracted_at)                                  as _extracted_at,
        any_value(_source_url)                              as _source_url
    from (
        select * from observado
        union all
        select * from orcamento
    )
    where cod_indicador in ('RECEITA_ESTADUAL', 'DESPESA_ESTADUAL', 'RESULTADO_ORCAMENTARIO')
      and sg_uf != 'BR'
    group by cod_indicador, ano
    having count(*) = 27   -- so' agrega ano completo; ano parcial nao vira "Brasil"

),

completo as (

    select * from observado
    union all
    select * from derivado
    union all
    select * from orcamento
    union all
    select * from nacional_somado

),

nacional as (

    select cod_indicador, ano, valor as valor_brasil
    from completo
    where sg_uf = 'BR'

),

regional as (

    -- media simples entre as UFs da regiao: e' um comparador de contexto, nao um
    -- agregado ponderado. Rotulado como tal na tela e em docs/METODOLOGIA.md.
    select
        c.cod_indicador,
        c.ano,
        u.regiao,
        avg(c.valor) as valor_regiao
    from completo as c
    inner join {{ ref('dim_uf') }} as u using (sg_uf)
    where c.sg_uf != 'BR'
    group by 1, 2, 3

)

select
    c.cod_indicador,
    c.sg_uf,
    u.regiao,
    c.ano,
    c.valor,
    n.valor_brasil,
    r.valor_regiao,
    c.unidade,
    c.fonte,
    c.n_periodos,
    c._extracted_at,
    c._source_url
from completo as c
left join {{ ref('dim_uf') }} as u using (sg_uf)
left join nacional as n
  on  n.cod_indicador = c.cod_indicador
  and n.ano           = c.ano
left join regional as r
  on  r.cod_indicador = c.cod_indicador
  and r.ano           = c.ano
  and r.regiao        = u.regiao
