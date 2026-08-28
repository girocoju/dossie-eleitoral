{{
  config(
    materialized = 'view',
    description  = 'Parlamentares em exercicio com a chave de pessoa que liga ao TSE (F-15).'
  )
}}

/*
  Ponte de identidade entre as Casas legislativas e o cadastro eleitoral.

  Este modelo NAO resolve `id_pessoa` — ele so' entrega as duas chaves possiveis,
  `cpf_hash` e `chave_nome_nascimento`. Quem resolve e' `dim_parlamentar`, que tem
  acesso ao cadastro do TSE.

  A separacao nao e' preciosismo. A primeira versao calculava `id_pessoa` aqui com
  a mesma formula de `dim_candidato` e casou 513 de 513 deputados e 1 de 81
  senadores. O motivo: no TSE o senador TEM CPF, entao o `id_pessoa` dele e' o
  cpf_hash; do lado do Senado nao ha' CPF, entao so' da' para calcular o hash de
  nome. Duas chaves corretas que nunca se encontram. Resolver exige olhar as duas
  pontas ao mesmo tempo, e e' isso que o mart faz.

  A diferenca entre as Casas viaja no dado, nao num comentario:

    Camara  publica CPF   -> casamento exato,      casamento_confiavel = true
    Senado  nao publica   -> nome + nascimento,    casamento_confiavel = false

  Uma tela que mostre atividade de senador carrega a marca de que a identidade foi
  inferida. Homonimia com mesma data de nascimento e' improvavel, mas nao e'
  impossivel, e o painel nao pode afirmar o que a fonte nao afirma.
*/

with base as (

    select
        casa,
        id_casa,
        nome_parlamentar,
        nome_completo,
        nome_normalizado,
        safe_cast(left(data_nascimento, 10) as date)  as data_nascimento,
        sexo,
        sigla_partido,
        sg_uf,
        cpf_hash,
        metodo_casamento,
        casamento_confiavel,
        url_perfil,
        _extracted_at
    from {{ source('raw_legislativo', 'parlamentares') }}

)

select
    casa,
    id_casa,
    nome_parlamentar,
    nome_completo,
    nome_normalizado,
    data_nascimento,
    sexo,
    sigla_partido,
    sg_uf,
    cpf_hash,
    metodo_casamento,
    casamento_confiavel,
    url_perfil,
    -- Sempre pelo nome, mesmo quando ha' CPF: e' a chave que casa com a coluna de
    -- mesmo nome em `dim_candidato`, e la' ela tambem ignora o CPF.
    case
        when nome_completo is not null and data_nascimento is not null
            then to_hex(sha256(concat(
                {{ sem_acento('nome_completo') }}, '|', cast(data_nascimento as string)
            )))
    end                                               as chave_nome_nascimento,
    _extracted_at
from base
