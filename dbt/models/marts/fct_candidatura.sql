{{
  config(
    materialized  = 'table',
    partition_by  = {'field': 'ano_eleicao', 'data_type': 'int64',
                     'range': {'start': 1998, 'end': 2032, 'interval': 4}},
    cluster_by    = ['cod_cargo', 'sg_uf', 'sigla_partido'],
    description   = 'Uma candidatura por linha (SPEC 5). Grao: sq_candidato.'
  )
}}

/*
  Grao: uma candidatura = candidato x cargo x UF x ano, ou seja, `sq_candidato`.
  A fonte tem uma linha por turno; aqui elas viram uma, guardando:
    - os atributos do 1o turno (partido, coligacao, situacao do registro);
    - o desfecho do ULTIMO turno disputado (`situacao_turno`), que e' o que diz
      se a pessoa foi eleita.

  Sobre `is_reeleicao` — conferido no pacote real de 2026: `ST_REELEICAO` vem `#NE`
  para todas as candidaturas enquanto a eleicao nao ocorre. Por isso a flag e'
  DERIVADA: e' reeleicao quando a pessoa esta' exercendo, no ano da eleicao, um
  mandato do mesmo cargo na mesma unidade eleitoral. `reeleicao_declarada` guarda
  o que a fonte disse, para quem quiser auditar a diferenca.

  `votos_nominais` fica NULL enquanto a ingestao de `votacao_candidato_munzona`
  (S4) nao for habilitada — ver docs/LACUNAS.md. A coluna existe desde ja' para
  que o modelo do Power BI nao mude quando o dado chegar.
*/

with candidaturas as (

    select * from {{ ref('stg_tse__candidaturas') }}

),

por_candidatura as (

    select
        sq_candidato,
        any_value(ano_eleicao)                                    as ano_eleicao,
        max(nr_turno)                                             as turnos_disputados,

        -- atributos estaveis: vem do 1o turno
        any_value(cod_cargo    having min nr_turno)               as cod_cargo,
        any_value(sg_uf        having min nr_turno)               as sg_uf,
        any_value(sg_ue        having min nr_turno)               as sg_ue,
        any_value(nm_ue        having min nr_turno)               as nm_ue,
        any_value(sigla_partido having min nr_turno)              as sigla_partido,
        any_value(nr_partido   having min nr_turno)               as nr_partido,
        any_value(sq_coligacao having min nr_turno)               as sq_coligacao,
        any_value(nome_coligacao having min nr_turno)             as nome_coligacao,
        any_value(composicao_coligacao having min nr_turno)       as composicao_coligacao,
        any_value(sg_federacao having min nr_turno)               as sg_federacao,
        any_value(situacao_candidatura having min nr_turno)       as situacao_candidatura,
        any_value(situacao_julgamento having min nr_turno)        as situacao_julgamento,
        any_value(situacao_cassacao having min nr_turno)          as situacao_cassacao,
        any_value(reeleicao_declarada having min nr_turno)        as reeleicao_declarada,
        any_value(despesa_max_campanha having min nr_turno)       as despesa_max_campanha,

        -- desfecho: vem do ultimo turno disputado
        any_value(situacao_turno having max nr_turno)             as situacao_turno,
        logical_or(foi_eleito)                                    as foi_eleito,

        any_value(_extracted_at having max nr_turno)              as _extracted_at
    from candidaturas
    group by sq_candidato

),

bens as (

    select
        sq_candidato,
        sum(valor_bem)   as total_bens_declarados,
        count(*)         as n_bens
    from {{ ref('stg_tse__bens') }}
    group by sq_candidato

),

pessoas as (

    select sq_candidato, id_pessoa, link_confiavel
    from {{ ref('dim_candidato') }}

),

-- mandatos em curso no ano da eleicao, usados so' para derivar `is_reeleicao`
mandatos_vigentes as (

    select distinct
        id_pessoa,
        cod_cargo,
        sg_ue,
        ano_eleicao as ano_eleicao_origem,
        ano_inicio,
        ano_fim
    from {{ ref('fct_mandato') }}

)

select
    c.sq_candidato,
    c.ano_eleicao,
    p.id_pessoa,
    p.link_confiavel,
    c.cod_cargo,
    c.sg_uf,
    c.sg_ue,
    c.nm_ue,
    c.sigla_partido,
    c.nr_partido,
    c.sg_federacao,
    c.sq_coligacao,
    c.nome_coligacao,
    c.composicao_coligacao,
    c.situacao_candidatura,
    c.situacao_julgamento,
    c.situacao_cassacao,
    c.turnos_disputados,
    c.situacao_turno,
    c.foi_eleito,

    -- reeleicao derivada do historico; ver comentario no topo
    coalesce(m.id_pessoa is not null, false)              as is_reeleicao,
    c.reeleicao_declarada,

    coalesce(b.total_bens_declarados, 0)                  as total_bens_declarados,
    coalesce(b.n_bens, 0)                                 as n_bens,
    b.sq_candidato is not null                            as declarou_algum_bem,
    c.despesa_max_campanha,

    cast(null as int64)                                   as votos_nominais,

    c._extracted_at

from por_candidatura as c
left join bens     as b using (sq_candidato)
left join pessoas  as p using (sq_candidato)
left join mandatos_vigentes as m
  on  m.id_pessoa  = p.id_pessoa
  and m.cod_cargo  = c.cod_cargo
  and m.sg_ue      = c.sg_ue
  -- o mandato tem de estar em curso NO ano da eleicao
  and c.ano_eleicao between m.ano_inicio and m.ano_fim
