/*
  O vice tem que ser o vice DAQUELE titular.

  `dim_chapa` liga duas pessoas reais. Um vinculo errado nao produz pagina
  quebrada: produz uma afirmacao falsa sobre DUAS pessoas ao mesmo tempo — diz
  que uma concorre com a outra quando nao concorre.

  A juncao usa `sq_candidato`, que e' inequivoco. Este teste confere o resultado
  contra a outra ponta: o nome de urna que o DivulgaCandContas devolveu tem que
  bater com o que o pacote em lote do TSE traz para o mesmo `sq_candidato`.

  DIVERGENCIA COSMETICA NAO CONTA. Medido em 30/08/2026, sao cinco casos e todos
  de grafia, nao de identidade:

      FREDERICO D'AVILA   x  FREDERICO D AVILA     apostrofo removido em lote
      PROFª MEIRE REIS    x  PROF. MEIRE REIS      abreviacao diferente
      CONCEICAO DO ENTORNO x CONCEICAO ALVES       nome de urna alterado

  Por isso a comparacao normaliza acento, pontuacao e caixa, e exige que o
  PRIMEIRO NOME coincida. Trocar Alckmin por outra pessoa mudaria o primeiro
  nome; trocar `PROFª` por `PROF.` nao.

  Teto de 15 divergencias, e nao zero: o TSE altera nome de urna ate' a eleicao,
  e um teto baixo transforma evento normal em job vermelho. Um salto acima disso
  significa que a juncao quebrou.
*/

with normalizado as (

    select
        sk_titular,
        nome_urna_vice,
        nome_urna_vice_na_fonte,
        -- Primeiro token de cada lado, sem acento e sem pontuacao.
        regexp_extract(
            regexp_replace({{ sem_acento('nome_urna_vice') }}, r"[^A-Z ]", ""),
            r"^\s*(\S+)") as primeiro_mart,
        regexp_extract(
            regexp_replace({{ sem_acento('nome_urna_vice_na_fonte') }}, r"[^A-Z ]", ""),
            r"^\s*(\S+)") as primeiro_fonte
    from {{ ref('dim_chapa') }}
    where vice_encontrado
      and nome_urna_vice is not null
      and nome_urna_vice_na_fonte is not null

),

suspeitos as (

    select count(*) as n
    from normalizado
    where primeiro_mart != primeiro_fonte

)

select n as vinculos_suspeitos
from suspeitos
where n > 15
