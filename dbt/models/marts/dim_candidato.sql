{{
  config(
    materialized = 'table',
    cluster_by   = ['sg_uf', 'cod_cargo'],
    description  = 'Uma linha por candidatura-pessoa (chave sq_candidato), com a chave de pessoa que liga os anos.'
  )
}}

/*
  Grao: `sq_candidato` — a chave do TSE, que ja' e' unica entre anos.
  A dimensao guarda o retrato da pessoa NAQUELA eleicao (idade, instrucao e
  ocupacao mudam entre pleitos), e nao um "estado atual".

  A chave que liga a mesma pessoa entre anos e' `id_pessoa` (SPEC 5 / ADR-005):

    1. `cpf_hash` quando o ano traz CPF (conferido: 2026 traz);
    2. fallback = hash de nome_completo normalizado + data de nascimento;
    3. nenhum dos dois -> `id_pessoa` NULL e a candidatura nao entra em
       `fct_mandato`, porque nao ha' como afirmar que e' a mesma pessoa.

  `link_confiavel = false` marca o caso 2. O Power BI mostra esse aviso sempre que
  a trajetoria de uma pessoa depender do fallback — o leitor precisa saber que
  homonimo com mesma data de nascimento existe.
*/

with candidaturas as (

    select *
    from {{ ref('stg_tse__candidaturas') }}
    -- o retrato da pessoa vem do 1o turno; o 2o turno repete os mesmos dados
    qualify row_number() over (partition by sq_candidato order by nr_turno) = 1

),

com_chave as (

    select
        *,
        case
            when cpf_hash is not null then cpf_hash
            when nome_completo is not null and data_nascimento is not null
                then to_hex(sha256(concat(
                    {{ sem_acento('nome_completo') }}, '|', cast(data_nascimento as string)
                )))
        end                                                       as id_pessoa,
        cpf_hash is not null                                      as link_confiavel
    from candidaturas

)

select
    sq_candidato,
    ano_eleicao,
    id_pessoa,
    link_confiavel,
    cpf_hash,
    nome_completo,
    nome_urna,
    nome_social,
    data_nascimento,
    sg_uf_nascimento,
    -- idade na posse (1o de janeiro do ano seguinte a eleicao), nao idade "hoje":
    -- e' o numero comparavel entre eleicoes
    date_diff(date(ano_eleicao + 1, 1, 1), data_nascimento, year) as idade_na_posse,
    genero,
    cor_raca,
    grau_instrucao,
    estado_civil,
    ocupacao,
    etnia_indigena,
    quilombola,
    cod_cargo,
    sg_uf,
    sg_ue,
    sigla_partido,
    _extracted_at
from com_chave
