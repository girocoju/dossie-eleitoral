# ADR-046 — Emendas parlamentares: uma linha por ano, e nenhum total

**Status:** Aceita · **Data:** 2026-09-04 · **Relacionada:** F-27, ADR-014, Constituição §0.1, Regra 5, Regra 6

## Contexto

Emenda parlamentar é o instrumento pelo qual um parlamentar destina recurso do
orçamento federal. É a informação de maior interesse público que faltava na
ficha, e a de maior risco: **atribuir milhões de reais a quem não propôs é uma
acusação publicada sobre uma pessoa real**.

Fonte: download em lote do Portal da Transparência (CGU). A API exige chave
cadastrada; o arquivo em bloco não exige nada.

## O erro que quase entrou: treze cópias do mesmo arquivo

O endereço é `/download-de-dados/emendas-parlamentares/{ano}`, e a suposição
óbvia — um arquivo por ano — está errada. **O Portal ignora o ano.** Conferido
baixando os treze:

```
13 downloads · 32.328.954 bytes cada · 1 sha256 distinto
```

A primeira versão carregou os treze: **1.228.019 linhas**, treze cópias das
94.463. Nada teria falhado. A carga terminaria verde, e toda soma por autor
sairia multiplicada por treze.

O que denunciou foi a **contagem idêntica em todos os anos** no log. Número que
se repete exato treze vezes não é coincidência.

O arquivo é **cumulativo**: 94.463 linhas, uma por (emenda, destino), cobrindo
emendas de 2014 a 2026, com o valor já acumulado. O ano de verdade é a coluna
`Ano da Emenda`.

## Decisão

Grão do mart: `(id_pessoa, ano_emenda, tipo)`. **Uma linha por ano, e nenhum
total de carreira.**

"Moveu R$ 300 milhões" sem dizer em quantos anos é um número grande e sem
significado — num mandato ou em quatro muda tudo. O ano é o que dá escala à
cifra, e por isso ele fica na chave e a tela não tem linha de soma. É menos
impressionante e é o único jeito de o número ser verdadeiro.

**Empenhado e pago aparecem separados.** Empenhar é reservar no orçamento; pagar
é sair da conta. Entre os autores identificados são R$ 149,1 bi empenhados contra
R$ 97,3 bi pagos — mostrar só um dos dois esconderia metade da história, e seria
sempre o número maior.

## O que não entra em ficha nenhuma

| | linhas | |
|---|---|---|
| **Autoria não publicada** | 15.962 | 17% do arquivo, R$ 18,5 bi pagos ([L-29](../LACUNAS.md)) |
| **Relator geral, bancada, comissão** | 4.645 | assinatura de colegiado, não de pessoa |
| **Nome ambíguo** | 369 | 7 autores que resolvem para mais de uma pessoa |

Os sete ambíguos são homonímia de verdade: **RICARDO IZAR** (pai e filho, os dois
deputados), ATILA LIRA, JOÃO CARLOS BACELAR, BEBETO.

## O casamento é por nome, e a marca viaja com o dado

O Portal publica o nome do autor no formato de `nome_parlamentar` e um código
próprio, sem relação com CPF nem com o identificador da Câmara. O casamento é por
nome normalizado, contra `dim_parlamentar` inteira.

```
nome único            1.302 autores ·  68.366 linhas   (93%)
nome AMBÍGUO              7 autores ·     369 linhas   ( 0%)
sem correspondência     235 autores ·   5.121 linhas
```

## Conferência (Regra 6)

**Contra o próprio CSV, somado em Python sem passar pelo BigQuery** — isso pega
erro de modelagem, que é onde o risco está:

| | CSV | mart |
|---|---|---|
| linhas de origem | 68.366 | 68.366 |
| valor pago | R$ 97,345 bi | R$ 97,345 bi |
| valor empenhado | R$ 149,082 bi | R$ 149,082 bi |

**Contra a cota anual de emendas individuais, que é pública.** É o teste que
vale: se o casamento de autoria estivesse errado, a mediana por parlamentar
sairia absurda.

| ano | mediana por parlamentar | teto da LDO |
|---|---|---|
| 2019 | R$ 15,0 mi | ~R$ 15 mi |
| 2020 | R$ 15,8 mi | R$ 16,2 mi |
| 2021 | R$ 16,2 mi | R$ 17,5 mi |
| 2022 | R$ 18,4 mi | R$ 18,3 mi |

Quatro anos colados no teto publicado. **De 2023 em diante os valores são bem
maiores** (R$ 32,1 mi em 2023, R$ 42,4 mi em 2025) e este projeto **não
verificou** a cota desses anos — fica como pergunta em aberto no SPEC §11, não
como conclusão.

## Não é ranking

Nenhuma tela ordena parlamentar por valor de emenda. O próprio comando `verify`
recusa fazê-lo, com o motivo escrito: ranking de político por dinheiro é placar,
e a Constituição §0.1 proíbe.
