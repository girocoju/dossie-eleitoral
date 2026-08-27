{{
  config(
    materialized = 'table',
    description  = 'Cargos do TSE com esfera, duracao de mandato e vagas em disputa em 2026.'
  )
}}

/*
  O seed `cargo_tse` guarda o que e' estavel (nome, esfera, duracao do mandato,
  se entra no modulo "Durante o mandato"). As vagas de 2026 vem do proprio TSE
  (`consulta_vagas`), somadas sobre as unidades eleitorais — nao sao digitadas a
  mao, senao quebrariam a Constituicao 0.4 (reprodutivel do zero).

  Codigos conferidos contra o pacote real de 2026 em 27/08/2026: os arquivos
  trazem os cargos 1 a 10 (Presidente e Vice, Governador e Vice, Senador,
  1o e 2o Suplente, Deputado Federal, Estadual e Distrital).
*/

with cargos as (

    select * from {{ ref('cargo_tse') }}

),

vagas_2026 as (

    select
        cod_cargo,
        sum(qt_vagas) as vagas_2026
    from {{ ref('stg_tse__vagas') }}
    where ano_eleicao = {{ var('ano_eleicao_atual') }}
    group by cod_cargo

)

select
    c.cod_cargo,
    c.descricao,
    c.esfera,
    c.duracao_mandato_anos,
    c.titular,
    c.no_escopo_mvp,
    c.modulo_durante_mandato,
    c.observacao,
    v.vagas_2026
from cargos as c
left join vagas_2026 as v using (cod_cargo)
