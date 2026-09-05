# ADR-050 — Registro sem CPF não é prova de uma segunda pessoa

**Data:** 05/09/2026
**Situação:** aceito
**Fecha:** L-31

## Contexto

A L-31 registrou que a presidência em curso da Comissão de Agricultura e Reforma
Agrária do Senado existe no dado e **não pode ser exibida**: o titular, Zequinha
Marinho, tem `metodo_id_pessoa = 'ambiguo'`, e vínculo com identidade ambígua não
entra em mart nenhum.

O diagnóstico escrito na lacuna foi **homonímia** — duas pessoas diferentes com o
mesmo nome e a mesma data de nascimento —, e a saída proposta foi usar a UF como
critério de desempate.

**As duas coisas estavam erradas.** As duas identidades que respondem pela chave
dele são:

| `id_pessoa` | nome | UF | anos |
|---|---|---|---|
| `e8bb01d2…` | JOSÉ DA CRUZ MARINHO | PA | 2002, 2006, 2010, 2014, 2018, 2022, 2026 |
| `96d30396…` | JOSÉ DA CRUZ MARINHO | PA | 1998 |

A UF é a mesma nos dois, então o desempate proposto não resolveria nada. E o
segundo `id_pessoa` é, byte a byte, **a própria `chave_nome_nascimento`**.

## A causa

`id_pessoa` é o `cpf_hash` quando o ano publica CPF e a chave de nome quando não
publica (ADR-005). O CPF é quase universal no cadastro do TSE — 100% em 2006,
2010 e 2026 —, mas **96,9% em 1998**: 459 registros daquele ano caem no fallback.

A consequência é que a mesma pessoa fica com **dois `id_pessoa`** quando tem
candidatura dos dois lados dessa fronteira. Contar identidades distintas lê isso
como homonímia.

Medido em 05/09/2026 sobre 131.567 chaves de nome + nascimento:

| chaves com mais de um `id_pessoa` | 326 |
|---|---|
| um id por CPF + um pelo fallback | **210** |
| dois ou mais ids por CPF | 116 |

Das 210, **204 não têm um único ano em comum** entre os dois ids, e 183
concorreram sempre na mesma UF. É a assinatura de um registro antigo sem CPF, não
a de duas pessoas.

## Decisão

**A contagem que decide a ambiguidade passa a ser a de identidades com CPF.**

```
ids_com_cpf = 1                      -> resolve para ela
ids_com_cpf = 0 e ids_sem_cpf = 1    -> resolve para a única sem CPF
qualquer outro caso                  -> ambíguo, id_pessoa NULL
```

**Isto não funde ninguém.** O `id_pessoa` de cada candidatura continua o que era,
e o registro sem CPF segue com o dono que tinha. O que muda é apenas a leitura:
ausência de CPF deixa de ser tratada como evidência de outra pessoa.

E a regra que a lacuna original protegia continua de pé: **duas identidades com
CPF na mesma chave são duas pessoas, e a chave é recusada.** São os 116 casos de
homonímia real, e nenhum deles passa a ser exibido por esta decisão.

## Por que a identidade com CPF, e não a outra

O parlamentar está em exercício **hoje**. A candidatura que o elegeu é recente, e
ano recente publica CPF — então a identidade com CPF é necessariamente a dele. A
sem CPF é um registro de 1998 que pode ser dele ou não; esta decisão não afirma
nem uma coisa nem outra sobre aquele registro.

Ficar com a identidade sem CPF seria o erro grave: penduraria o mandato de um
parlamentar de hoje num registro antigo que pode não ser dele, sem nada na tela
indicando isso. É essa direção que o teste
`assert_registro_sem_cpf_nao_desloca_identidade` guarda — olhando o resultado, e
não o texto da regra, para falhar também se alguém inverter as duas condições do
`case`.

## Alcance

Um parlamentar sai de `ambiguo` — Zequinha Marinho, e com ele a presidência da
CRA passa a aparecer. Os 1.991 deputados já resolviam por CPF e não são tocados;
os outros 80 senadores já resolviam por nome.

`chave_partida` fica gravada em `dim_parlamentar` para que a medição acima possa
ser refeita sem reconstruir a consulta.

## Consequências

- A L-31 fecha um dia depois de aberta, como a L-30 — e pela mesma razão: a
  premissa da lacuna não se sustentava.
- Fica o padrão que já apareceu três vezes seguidas: **a lacuna descrevia
  corretamente um sintoma e errava a causa.** L-28 mediu identidade e concluiu
  que faltava fonte; L-30 mediu um endpoint e concluiu que faltava dado; L-31
  mediu ambiguidade e concluiu que havia homônimo. Nas três, o passo que faltava
  era olhar *por que* o número era aquele.
- Nada muda para quem tem CPF em todas as candidaturas, que é a esmagadora
  maioria.
