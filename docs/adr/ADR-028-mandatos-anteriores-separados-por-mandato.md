# ADR-028 — "Durante mandatos anteriores" separa por mandato

**Status:** Aceita · **Data:** 2026-08-31 · **Relacionada:** ADR-024 (atividade de mandatos anteriores), ADR-023 (ausência não é afirmação), F-06

## Contexto

O bloco socioeconômico das fichas juntava **todos** os mandatos de uma pessoa numa
tabela única, sob um `h2` que nomeava apenas o mandato da **primeira linha**:

    Durante mandatos anteriores — BRASIL, 2023–2026

A ficha do Lula trazia **35 linhas de três mandatos presidenciais** (2003–2006,
2007–2010, 2023–2026) sob esse título. "Produto Interno Bruto" aparecia três
vezes, e a única forma de saber a qual mandato cada linha pertencia era inferir
pela coluna Janela — que nem sempre coincide com o mandato, porque é o intervalo
em que a fonte publicou dado.

Medido em 31/08/2026: **57 dos 129** candidatos com este bloco têm mais de um
mandato. Para todos eles o título afirmava um período que não descrevia a tabela.

É a mesma família de erro do ADR-023: o dado está certo, o **rótulo** é que
afirma algo falso. Nenhum teste pega isso — `dbt build` verde, o número correto
em cada célula, e a tela dizendo outra coisa.

## Decisão

Um bloco por mandato, **do mais recente para o mais antigo**, cada um com título
próprio no formato `Cargo · Unidade · início–fim`. Dentro de cada bloco, os
indicadores em **ordem alfabética**.

O `h2` passa a ser apenas "Durante mandatos anteriores", sem período: quem afirma
o período é o `h3` de cada bloco, e aí a afirmação é verdadeira.

### A coluna "No cargo de" saiu

O título do bloco já diz o cargo. Repetir a informação em toda linha gastava uma
das cinco colunas — e cinco colunas numa tabela de ficha apertam no celular, que
é onde está a maior parte do acesso (ADR-018).

### A ordem alfabética é a do nome EXIBIDO

O glossário troca o nome de origem pelo nome de tela: "Produto Interno Bruto a
preços correntes" vira "PIB do estado", "Taxa de desocupação" vira "Desemprego".
Ordenar por `i.nome` no SQL — que era o que existia — produziria na tela uma
sequência que parece aleatória. A ordenação passou para a renderização, sobre o
rótulo final e sem acento; o `order by` do SQL ficou só para a saída ser
determinística, com o motivo escrito ao lado.

## Consequências

- Fichas de quem teve vários mandatos ficam mais longas em altura de título, e
  legíveis pela primeira vez como trajetória.
- Quem teve um mandato só vê praticamente a mesma tela de antes, com uma coluna
  a menos e o período no `h3` em vez do `h2`.
- A janela de cada indicador continua visível por linha, porque ela **não** é o
  mandato — e o texto de abertura do bloco passa a dizer isso.
