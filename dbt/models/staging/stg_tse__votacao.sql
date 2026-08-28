{{ config(materialized = 'view', description = 'Votos por candidatura e turno (S4), ja agregados na ingestao.') }}

/*
  Grao: uma candidatura por turno. A fonte tem grao municipio x zona x voto em
  transito — cerca de 10 milhoes de linhas por eleicao, ~2 GB somando os sete
  pleitos. A soma acontece na INGESTAO (ver `agregar_por` no layout), e o
  BigQuery recebe dezenas de milhares de linhas em vez de dezenas de milhoes.

  Sobre qual coluna de voto usar: em 1998 o TSE publica `QT_VOTOS_NOMINAIS`
  ZERADO e o valor em `QT_VOTOS_NOMINAIS_VALIDOS` — conferido no Acre: 0 contra
  762.844. Nos anos recentes a populada e' a primeira. Por isso as duas sao
  somadas na ingestao e a escolha acontece aqui, com regra explicita.

  Validacao contra a historia (1998, 1o turno): FHC 35.936.382, Lula 21.475.211,
  Ciro 7.426.187 — batem com o resultado oficial.
*/

with por_uf as (

    select
        ano_eleicao,
        cd_eleicao,
        {{ inteiro('cod_cargo') }}          as cod_cargo,
        sq_candidato,
        {{ inteiro('nr_turno') }}           as nr_turno,
        /*
          A unidade DISPUTADA, que compoe a `sk_candidatura`. A fonte registra
          onde o voto foi DEPOSITADO — para presidente, as 27 UFs mais `ZZ`
          (exterior). Numa eleicao geral todo cargo e' disputado no ambito da UF,
          menos a presidencia, que e' nacional.
        */
        if({{ inteiro('cod_cargo') }} = 1, 'BR', sg_uf)       as sg_ue,
        -- a coluna populada varia por ano; a regra fica explicita, nao escondida
        if(
            coalesce(qt_votos_nominais, 0) > 0,
            qt_votos_nominais,
            qt_votos_nominais_validos
        )                                    as votos,
        n_linhas_agregadas,
        _extracted_at,
        _source_url
    from {{ source('raw_tse', 'votacao') }}
    where sq_candidato is not null
      and sg_uf is not null

)

select
    {{ sk_candidatura(sg_ue='sg_ue') }}      as sk_candidatura,
    ano_eleicao,
    cd_eleicao,
    sg_ue,
    cod_cargo,
    sq_candidato,
    nr_turno,
    sum(votos)                               as votos_nominais,
    sum(n_linhas_agregadas)                  as n_linhas_agregadas,
    max(_extracted_at)                       as _extracted_at,
    any_value(_source_url)                   as _source_url
from por_uf
group by
    ano_eleicao, cd_eleicao, sg_ue, cod_cargo, sq_candidato, nr_turno
