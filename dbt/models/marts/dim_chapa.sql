{{
  config(
    materialized = 'table',
    cluster_by   = ['sk_titular'],
    description  = 'Quem concorre com quem: titular e seus vices ou suplentes (F-21).'
  )
}}

/*
  Grao: (sk_titular, sk_vice).

  O QUE ESTE MODELO ACRESCENTA E' O VINCULO, NAO A PESSOA

  Vice e suplente ja' estao em `dim_candidato` com candidatura propria, foto e
  perfil: 13 vice-presidentes, 203 vice-governadores e 661 suplentes de senador
  em 2026. O que nao existe no pacote em lote do TSE e' a CHAPA.

  Sem isto, Geraldo Alckmin esta' na base como candidato a Vice-Presidente pelo
  PSB e nada diz que ele concorre com Lula. O vinculo so' aparece no
  DivulgaCandContas, uma consulta por chapa (`ingest.chapas`).

  Por isso aqui nao ha' nome, partido nem foto: eles vem de `dim_candidato` na
  junção. Copiar criaria uma segunda versao da verdade, que envelheceria sozinha
  enquanto o TSE ainda altera cadastro.

  CONFERENCIA CONTRA A FONTE EM LOTE

  A ingestao guarda `nome_urna_vice` so' para este teste: se o nome que o
  DivulgaCandContas devolveu nao bater com o de `dim_candidato` para o mesmo
  `sq_candidato`, o vinculo esta' apontando para a pessoa errada — e um vice
  atribuido ao titular errado e' uma afirmacao falsa sobre duas pessoas de uma
  vez. `assert_chapa_aponta_para_a_pessoa_certa` trava isso.
*/

with chapas as (

    select
        sk_titular,
        {{ limpa('sq_vice') }}          as sq_vice,
        ordem,
        {{ limpa('cargo_vice') }}       as cargo_vice,
        {{ limpa('nome_urna_vice') }}   as nome_urna_vice_na_fonte,
        ano_eleicao,
        _extracted_at
    from {{ source('raw_tse', 'chapas') }}
    qualify row_number() over (
        partition by sk_titular, sq_vice order by _extracted_at desc) = 1

),

candidatos as (

    select sk_candidatura, sq_candidato, nome_urna, nome_completo,
           sigla_partido, cod_cargo, url_foto, id_pessoa
    from {{ ref('dim_candidato') }}

)

select
    c.sk_titular,
    t.nome_urna                     as nome_urna_titular,
    t.cod_cargo                     as cod_cargo_titular,

    v.sk_candidatura                as sk_vice,
    c.sq_vice,
    c.ordem,
    c.cargo_vice,
    v.nome_urna                     as nome_urna_vice,
    v.nome_completo                 as nome_completo_vice,
    v.sigla_partido                 as sigla_partido_vice,
    v.cod_cargo                     as cod_cargo_vice,
    v.url_foto                      as url_foto_vice,
    v.id_pessoa                     as id_pessoa_vice,

    -- FALSE quando o `sq_candidato` do vinculo nao existe em `dim_candidato`.
    -- Acontece se o TSE publicar a chapa antes do cadastro, ou depois de a
    -- candidatura sair da publicacao (L-23). A tela precisa saber para nao
    -- mostrar uma linha vazia.
    v.sk_candidatura is not null     as vice_encontrado,
    c.nome_urna_vice_na_fonte,
    c.ano_eleicao,
    c._extracted_at

from chapas c
join candidatos t on t.sk_candidatura = c.sk_titular
left join candidatos v on v.sq_candidato = c.sq_vice
                      and v.sk_candidatura like concat(cast(c.ano_eleicao as string), '-%')
