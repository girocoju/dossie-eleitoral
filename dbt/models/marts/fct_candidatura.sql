{{
  config(
    materialized  = 'table',
    partition_by  = {'field': 'ano_eleicao', 'data_type': 'int64',
                     'range': {'start': 1998, 'end': 2032, 'interval': 4}},
    cluster_by    = ['cod_cargo', 'sg_uf', 'sigla_partido'],
    description   = 'Uma candidatura por linha (SPEC 5). Grao: sk_candidatura.'
  )
}}

/*
  Grao: uma candidatura = candidato x cargo x UF x ano, identificada por
  `sk_candidatura` (ano_eleicao + sg_ue + sq_candidato). `sq_candidato` sozinho nao
  serve: so' e' global a partir de 2010.
  A fonte tem uma linha por turno; aqui elas viram uma, guardando:
    - os atributos do 1o turno (partido, coligacao, situacao do registro);
    - o desfecho do ULTIMO turno disputado (`situacao_turno`), que e' o que diz
      se a pessoa foi eleita.

  Sobre `is_reeleicao` — conferido no pacote real de 2026: `ST_REELEICAO` vem `#NE`
  para todas as candidaturas enquanto a eleicao nao ocorre. Por isso a flag e'
  DERIVADA: e' reeleicao quando a pessoa esta' exercendo, no ano da eleicao, um
  mandato do mesmo cargo na mesma unidade eleitoral. `reeleicao_declarada` guarda
  o que a fonte disse, para quem quiser auditar a diferenca.

  `votos_nominais` vem de `votacao_candidato_munzona` (S4), agregado na ingestao.
  E' NULL para 2026 porque a eleicao ainda nao ocorreu — e nao por falta de dado.
*/

with candidaturas as (

    select * from {{ ref('stg_tse__candidaturas') }}

),

por_candidatura as (

    select
        sk_candidatura,
        any_value(sq_candidato)                                   as sq_candidato,
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
    group by sk_candidatura

),

bens as (

    select
        sk_candidatura,
        sum(valor_bem)   as total_bens_declarados,
        count(*)         as n_bens
    from {{ ref('stg_tse__bens') }}
    group by sk_candidatura

),

pessoas as (

    select sk_candidatura, id_pessoa, link_confiavel
    from {{ ref('dim_candidato') }}

),

votos as (

    select
        sk_candidatura,
        sum(votos_nominais)                                   as votos_nominais,
        max(if(nr_turno = 1, votos_nominais, null))           as votos_1o_turno,
        max(if(nr_turno = 2, votos_nominais, null))           as votos_2o_turno
    from {{ ref('stg_tse__votacao') }}
    group by sk_candidatura

),

propostas as (

    select
        sk_candidatura,
        tem_proposta_governo,
        n_arquivos_proposta,
        nome_arquivo_proposta,
        url_proposta_oficial
    from {{ ref('stg_tse__propostas') }}

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
    c.sk_candidatura,
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
    b.sk_candidatura is not null                          as declarou_algum_bem,
    c.despesa_max_campanha,

    /*
      Votos nominais somados dos dois turnos. `votos_1o_turno` e `votos_2o_turno`
      ficam separados porque somar os dois e' correto para "quantos votos recebeu
      no total", mas errado para comparar desempenho entre candidatos que
      disputaram numeros diferentes de turnos.
      NULL quando a eleicao ainda nao ocorreu — e' o caso de 2026 inteiro.
    */
    v.votos_nominais,
    v.votos_1o_turno,
    v.votos_2o_turno,

    /*
      F-14 — proposta de governo. Sao TRES estados, e a tela precisa distinguir
      os tres; campo vazio se le como omissao do candidato, o que seria injusto
      com 93% deles:

        proposta_obrigatoria = false  -> "nao se aplica a este cargo"
        obrigatoria e tem            -> link para a pagina oficial
        obrigatoria e nao tem        -> "nao consta"

      `proposta_obrigatoria` vem da LEI, nao do dado: Lei 9.504/97, art. 11,
      par. 1o, IX, que cita Prefeito, Governador e Presidente. SENADOR NAO ESTA
      NA LISTA, embora o cargo seja majoritario — e a medicao de 28/08/2026
      confirma (0 de 318 senadores tem proposta, contra 193 de 198 governadores).
      Marcar senador como "nao consta" seria acusa-lo de uma omissao inexistente.
    */
    c.cod_cargo in (1, 3)                                 as proposta_obrigatoria,
    coalesce(pr.tem_proposta_governo, false)              as tem_proposta_governo,
    coalesce(pr.n_arquivos_proposta, 0)                   as n_arquivos_proposta,
    pr.nome_arquivo_proposta,
    pr.url_proposta_oficial,

    c._extracted_at

from por_candidatura as c
left join bens     as b using (sk_candidatura)
left join pessoas  as p using (sk_candidatura)
left join votos    as v  using (sk_candidatura)
left join propostas as pr using (sk_candidatura)
left join mandatos_vigentes as m
  on  m.id_pessoa  = p.id_pessoa
  and m.cod_cargo  = c.cod_cargo
  and m.sg_ue      = c.sg_ue
  -- o mandato tem de estar em curso NO ano da eleicao
  and c.ano_eleicao between m.ano_inicio and m.ano_fim
