/*
  T-205 — relatorio de taxa de vinculacao de pessoa entre anos.

  Nao e' um modelo: e' uma analise para rodar sob demanda
  (`dbt compile --select relatorio_vinculacao_pessoa` e executar o SQL de
  `target/compiled/...`) quando se quiser saber quanto do historico realmente
  liga a mesma pessoa entre eleicoes.

  Le-se assim: `pct_por_cpf` alto significa que a trajetoria daquele ano e'
  confiavel; `pct_sem_chave` alto significa que aquele ano nao consegue entrar em
  `fct_mandato`, e a lacuna tem de ir para docs/LACUNAS.md — nunca ser preenchida
  por aproximacao de nome.
*/

with base as (

    select
        ano_eleicao,
        count(*)                                              as candidaturas,
        countif(cpf_hash is not null)                         as com_cpf,
        countif(cpf_hash is null and id_pessoa is not null)    as so_fallback,
        countif(id_pessoa is null)                            as sem_chave
    from {{ ref('dim_candidato') }}
    group by ano_eleicao

),

reaparicoes as (

    select
        ano_eleicao,
        count(distinct id_pessoa) as pessoas_vistas_em_outro_ano
    from {{ ref('dim_candidato') }} as d
    where id_pessoa is not null
      and exists (
        select 1
        from {{ ref('dim_candidato') }} as o
        where o.id_pessoa = d.id_pessoa
          and o.ano_eleicao != d.ano_eleicao
      )
    group by ano_eleicao

)

select
    b.ano_eleicao,
    b.candidaturas,
    b.com_cpf,
    b.so_fallback,
    b.sem_chave,
    round(100 * safe_divide(b.com_cpf, b.candidaturas), 1)      as pct_por_cpf,
    round(100 * safe_divide(b.so_fallback, b.candidaturas), 1)  as pct_por_fallback,
    round(100 * safe_divide(b.sem_chave, b.candidaturas), 1)    as pct_sem_chave,
    coalesce(r.pessoas_vistas_em_outro_ano, 0)                  as pessoas_vistas_em_outro_ano
from base as b
left join reaparicoes as r using (ano_eleicao)
order by b.ano_eleicao
