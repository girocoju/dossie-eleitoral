{{
  config(
    materialized = 'table',
    cluster_by   = ['cod_indicador', 'sg_uf'],
    description  = 'F-06 — o que aconteceu com cada indicador DURANTE a janela de um mandato. Nunca "resultado".'
  )
}}

/*
  ===================================================================
  ESTE MODELO NAO MEDE DESEMPENHO DE GOVERNO.
  ===================================================================

  Ele responde uma unica pergunta, e responde literalmente:
  "o que aconteceu com este indicador, nesta UF, entre o inicio e o fim desta
  janela de mandato — e o que aconteceu no Brasil e na regiao no MESMO periodo?"

  Correlacao nao e' causalidade (Constituicao 0.2). Nenhuma coluna daqui pode ser
  rotulada na tela como "resultado", "desempenho", "entrega" ou "nota". O nome
  `delta_vs_brasil` e' descritivo: e' a diferenca entre duas variacoes observadas,
  nada mais. Por isso tambem nao existe ranking nem score agregado neste modelo.

  Escopo (SPEC 2.2): so' Presidente e Governador (`modulo_durante_mandato` no
  seed de cargos). Para deputado e senador o vinculo individuo <-> indicador
  regional e' fraco demais, entao eles simplesmente nao aparecem aqui.

  ── Como as pontas da janela sao escolhidas ──

  `ano_referencia_inicio` e' o ano ANTERIOR a posse: e' a situacao herdada, o
  ponto de partida honesto. Se ele nao existir na serie, usa-se o primeiro ano
  disponivel dentro da janela e `base_e_heranca` fica FALSE.

  `ano_referencia_fim` e' o ultimo ano da serie que seja <= `ano_fim`. Indicador
  brasileiro tem defasagem (o PIB estadual sai com ~2 anos de atraso: em 08/2026 a
  serie termina em 2023), entao quando o ultimo ano disponivel e' anterior ao fim
  do mandato, `janela_incompleta` vira TRUE e a tela precisa dizer isso
  (SPEC 5, "Indicador com defasagem").
*/

with mandatos as (

    select
        sk_mandato,
        id_pessoa,
        sk_candidatura,
        nome_urna,
        nome_completo,
        cod_cargo,
        sigla_partido,
        sg_uf,
        nm_ue,
        ano_eleicao,
        ano_inicio,
        ano_fim,
        em_curso
    from {{ ref('fct_mandato') }}
    where modulo_durante_mandato          -- so' Presidente e Governador
      and titular

),

serie as (

    select
        cod_indicador,
        sg_uf,
        ano,
        valor,
        valor_brasil,
        valor_regiao,
        unidade,
        fonte,
        _extracted_at
    from {{ ref('fct_indicador_uf_ano') }}

),

-- todo ponto da serie que cai dentro da janela do mandato (incluindo o ano
-- anterior a posse, que e' a base preferida)
pontos as (

    select
        m.sk_mandato,
        m.ano_inicio,
        m.ano_fim,
        s.cod_indicador,
        s.ano,
        s.valor,
        s.valor_brasil,
        s.valor_regiao,
        s.unidade,
        s.fonte,
        s._extracted_at
    from mandatos as m
    inner join serie as s
      on  s.sg_uf = m.sg_uf
      and s.ano between m.ano_inicio - 1 and m.ano_fim

),

/*
  As pontas sao escolhidas por ARRAY_AGG ordenado, e nao por subconsulta
  correlacionada: o BigQuery so' aceita subconsulta correlacionada que ele consiga
  transformar em JOIN, e `ORDER BY ... LIMIT 1` por grupo nao e' um desses casos.
  `ARRAY_AGG(STRUCT(...) ORDER BY ano LIMIT 1)[OFFSET(0)]` faz o mesmo em uma
  unica passada de agregacao.
*/
pontas as (

    select
        sk_mandato,
        cod_indicador,
        ano_inicio,
        ano_fim,
        array_agg(
            struct(ano, valor, valor_brasil, valor_regiao) order by ano asc limit 1
        )[offset(0)]                                        as inicio,
        array_agg(
            struct(ano, valor, valor_brasil, valor_regiao) order by ano desc limit 1
        )[offset(0)]                                        as fim,
        any_value(unidade)                                  as unidade,
        any_value(fonte)                                    as fonte,
        max(_extracted_at)                                  as _extracted_at,
        countif(ano between ano_inicio and ano_fim)         as anos_com_dado
    from pontos
    group by sk_mandato, cod_indicador, ano_inicio, ano_fim

),

calculado as (

    select
        m.sk_mandato,
        m.id_pessoa,
        m.sk_candidatura,
        m.nome_urna,
        m.nome_completo,
        m.cod_cargo,
        m.sigla_partido,
        m.sg_uf,
        m.nm_ue,
        m.ano_eleicao,
        m.ano_inicio,
        m.ano_fim,
        m.em_curso,

        p.cod_indicador,
        p.unidade,
        p.fonte,

        p.inicio.ano                                    as ano_referencia_inicio,
        p.fim.ano                                       as ano_referencia_fim,
        p.inicio.valor                                  as valor_inicio,
        p.fim.valor                                     as valor_fim,
        p.inicio.valor_brasil                           as valor_brasil_inicio,
        p.fim.valor_brasil                              as valor_brasil_fim,
        p.inicio.valor_regiao                           as valor_regiao_inicio,
        p.fim.valor_regiao                              as valor_regiao_fim,
        p.anos_com_dado,

        p.fim.valor - p.inicio.valor                    as variacao_abs,
        {{ variacao_pct('p.fim.valor', 'p.inicio.valor') }}                 as variacao_pct,
        {{ variacao_pct('p.fim.valor_brasil', 'p.inicio.valor_brasil') }}   as variacao_brasil_pct,
        {{ variacao_pct('p.fim.valor_regiao', 'p.inicio.valor_regiao') }}   as variacao_regiao_pct,

        -- a ponta inicial e' mesmo o ano anterior a posse?
        p.inicio.ano = m.ano_inicio - 1                 as base_e_heranca,
        -- a serie chega ate' o fim do mandato?
        p.fim.ano < m.ano_fim                           as janela_incompleta,

        p._extracted_at
    from pontas as p
    inner join mandatos as m using (sk_mandato)

)

select
    *,
    -- diferenca entre a variacao da UF e a do Brasil no MESMO periodo.
    -- E' um contraste descritivo, nao um placar.
    case
        when variacao_pct is null or variacao_brasil_pct is null then null
        else variacao_pct - variacao_brasil_pct
    end                                                 as delta_vs_brasil,
    case
        when variacao_pct is null or variacao_regiao_pct is null then null
        else variacao_pct - variacao_regiao_pct
    end                                                 as delta_vs_regiao,
    -- texto que acompanha o registro para qualquer lugar que ele for exibido
    'Indicadores refletem o periodo; nao medem o efeito do mandato.' as aviso_metodologico
from calculado
where valor_inicio is not null
  and valor_fim is not null
  and ano_referencia_inicio < ano_referencia_fim
