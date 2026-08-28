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

  `link_confiavel = false` marca o caso 2. A ficha mostra esse aviso sempre que
  a trajetoria de uma pessoa depender do fallback — o leitor precisa saber que
  homonimo com mesma data de nascimento existe.
*/

with candidaturas as (

    select *
    from {{ ref('stg_tse__candidaturas') }}
    -- o retrato da pessoa vem do 1o turno; o 2o turno repete os mesmos dados
    qualify row_number() over (partition by sk_candidatura order by nr_turno) = 1

),

fotos as (

    select sk_candidatura, url_foto
    from {{ ref('stg_tse__fotos') }}

),

/*
  A chave por nome, calculada SEMPRE — inclusive para quem tem CPF.

  Existe para casar com fontes que nao publicam CPF. O Senado e' o caso: o
  `id_pessoa` de um senador aqui e' o cpf_hash, porque o TSE tem CPF; do lado do
  Senado so' da' para calcular o hash de nome + nascimento. Duas chaves corretas
  que nunca se encontram — na primeira medicao, 1 senador de 81 casou.

  Fica num CTE proprio para que `id_pessoa` seja DERIVADA dela, e nao uma segunda
  copia da mesma expressao. Com as duas escritas lado a lado, bastava alguem
  ajustar a normalizacao de uma e esquecer a outra para a ponte do Senado quebrar
  de novo, sem erro nenhum.
*/
com_chave_nome as (

    select
        *,
        case
            when nome_completo is not null and data_nascimento is not null
                then to_hex(sha256(concat(
                    {{ sem_acento('nome_completo') }}, '|', cast(data_nascimento as string)
                )))
        end                                                       as chave_nome_nascimento
    from candidaturas

),

com_chave as (

    select
        *,
        -- CPF quando a fonte publica; senao a chave por nome. A regra nao aparece
        -- escrita duas vezes em lugar nenhum.
        coalesce(cpf_hash, chave_nome_nascimento)                 as id_pessoa,
        cpf_hash is not null                                      as link_confiavel
    from com_chave_nome

)

select
    c.sk_candidatura,
    c.sq_candidato,
    c.ano_eleicao,
    c.id_pessoa,
    c.chave_nome_nascimento,
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
    /*
      Numero de urna. E' o que a pessoa digita para votar, e por isso a informacao
      mais pratica da ficha inteira — mais util, para quem vota, do que qualquer
      atributo declarado.

      A largura muda por cargo: 2 digitos em Presidente e Governador (o numero do
      partido), 3 em Senador, 4 em Deputado Federal, 5 em Estadual. Guardado como
      inteiro; quem exibe cuida do zero a' esquerda.
    */
    nr_candidato,

    -- F-13: a URL, nunca o binario (ADR-012). NULL quando a fonte nao publica foto.
    f.url_foto,
    f.url_foto is not null                                       as tem_foto,

    _extracted_at
from com_chave as c
left join fotos as f using (sk_candidatura)
