{{
  config(
    materialized = 'table',
    cluster_by   = ['sg_uf', 'cod_cargo'],
    description  = 'Uma linha por candidatura-pessoa (chave sk_candidatura), com a chave de pessoa que liga os anos.'
  )
}}

/*
  Grao: `sk_candidatura` = (ano_eleicao, sg_ue, sq_candidato). NAO e' `sq_candidato`
  sozinho: ele so' e' globalmente unico a partir de 2010 — em 2002 e 2006 o mesmo
  numero aparece em ate' 27 UFs. Ver o macro `sk_candidatura`.
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
    qualify row_number() over (partition by sk_candidatura order by nr_turno) = 1

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
    sk_candidatura,
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
    /*
      Idade na posse (1o de janeiro do ano seguinte a eleicao), e nao idade "hoje":
      e' o numero comparavel entre eleicoes.

      O cadastro do TSE tem erros de digitacao no campo de nascimento — conferido
      em 27/08/2026: 21 candidaturas em 180.718 (0,01%) resultam em idade
      impossivel. Ha' `7953-09-05` (ano 7953) e, em 1998, quinze pessoas com
      nascimento no proprio ano da eleicao, oito delas no DF com a mesma data
      (18/08/1998) — a data de registro vazou para o campo de nascimento.

      O projeto NAO corrige o dado (SPEC 9: nao preencher). Guarda o valor bruto em
      `idade_na_posse` e marca `idade_plausivel = false`; quem calcula estatistica
      usa `idade_na_posse_valida`, que e' NULL nesses casos. Assim a mediana nao e'
      contaminada por uma idade de -5.946 anos e o erro da fonte continua visivel.
      Ver docs/LACUNAS.md, L-15.
    */
    date_diff(date(ano_eleicao + 1, 1, 1), data_nascimento, year) as idade_na_posse,
    date_diff(date(ano_eleicao + 1, 1, 1), data_nascimento, year)
        between 17 and 110                                       as idade_plausivel,
    if(
        date_diff(date(ano_eleicao + 1, 1, 1), data_nascimento, year) between 17 and 110,
        date_diff(date(ano_eleicao + 1, 1, 1), data_nascimento, year),
        null
    )                                                            as idade_na_posse_valida,
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
