/*
  A ponte de identidade tem que cobrir quase todo mundo em exercicio.

  Se cair, a ficha de dezenas de candidatos perde a atividade parlamentar EM
  SILENCIO — a tela nao fica quebrada, fica vazia, e vazio parece "esse deputado
  nao fez nada". Esse e' o pior modo de falha do projeto inteiro: um erro de
  casamento vira uma afirmacao sobre uma pessoa.

  Ja' aconteceu uma vez, e por isso este teste existe: a primeira versao resolvia
  `id_pessoa` no staging e casou 513 de 513 deputados e 1 de 81 senadores. Os
  numeros nao levantavam suspeita nenhuma olhando so' a Camara.

  Piso de 95% por Casa. Abaixo disso e' erro de chave, nao rotatividade.
*/

with cobertura as (

    select
        casa,
        count(*)                                as total,
        countif(id_pessoa is not null)          as casados
    from {{ ref('dim_parlamentar') }}
    group by casa

)

select
    casa,
    total,
    casados,
    round(casados / total, 4) as taxa
from cobertura
where casados < total * 0.95
