{{
  config(
    materialized = 'table',
    cluster_by   = ['sg_uf', 'cod_cargo'],
    description  = 'Votos de cada candidatura por UF onde o voto foi depositado. Grao: candidatura x turno x UF.'
  )
}}

/*
  Grao: candidatura x turno x UF DE DEPOSITO do voto.

  Diferente de `fct_candidatura.votos_nominais`, que e' o total: aqui a votacao
  fica aberta por estado. E' o que responde "onde este candidato foi mais votado".

  Para presidente, a candidatura e' nacional (`sg_ue = 'BR'`) mas os votos vem das
  27 UFs mais `ZZ` (exterior) e, em 2010, `VT` (voto em transito, so' para
  presidente naquele ano — 11 linhas, 117.733 votos). Por isso `sg_uf` aqui NAO e'
  a unidade disputada: e' onde a urna estava.

  Nao ha' quebra por MUNICIPIO: a fonte tem, mas a agregacao acontece na ingestao
  para o warehouse nao receber ~10 milhoes de linhas por eleicao (SPEC S4,
  Constituicao 0.5). Ver docs/LACUNAS.md, L-19.
*/

with votos as (

    select
        ano_eleicao,
        {{ limpa('cd_eleicao') }}           as cd_eleicao,
        {{ limpa('sg_uf') }}                as sg_uf,
        {{ inteiro('cod_cargo') }}          as cod_cargo,
        sq_candidato,
        {{ inteiro('nr_turno') }}           as nr_turno,
        if({{ inteiro('cod_cargo') }} = 1, 'BR', sg_uf)          as sg_ue,
        if(
            coalesce(qt_votos_nominais, 0) > 0,
            qt_votos_nominais,
            qt_votos_nominais_validos
        )                                       as votos_nominais,
        n_linhas_agregadas,
        _extracted_at
    from {{ source('raw_tse', 'votacao') }}
    where sq_candidato is not null
      and sg_uf is not null

)

select
    {{ sk_candidatura(ano_eleicao='v.ano_eleicao', sg_ue='v.sg_ue', sq_candidato='v.sq_candidato') }} as sk_candidatura,
    v.ano_eleicao,
    v.sg_uf,
    u.nome                                      as nome_uf,
    u.regiao,
    v.cod_cargo,
    v.nr_turno,
    d.nome_urna,
    d.sigla_partido,
    v.votos_nominais,
    -- participacao do estado no total daquele candidato
    safe_divide(
        v.votos_nominais,
        sum(v.votos_nominais) over (partition by v.sq_candidato, v.ano_eleicao, v.nr_turno)
    ) * 100                                     as pct_do_total_do_candidato,
    v.n_linhas_agregadas,
    v._extracted_at
from votos as v
left join {{ ref('dim_uf') }} as u
       on u.sg_uf = v.sg_uf
left join {{ ref('dim_candidato') }} as d
       on d.sk_candidatura = {{ sk_candidatura(ano_eleicao='v.ano_eleicao', sg_ue='v.sg_ue', sq_candidato='v.sq_candidato') }}
