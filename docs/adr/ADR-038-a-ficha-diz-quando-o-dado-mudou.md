# ADR-038 — A ficha diz quando o dado mudou, não quando o site rodou

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** Constituição §0.3, ADR-037, F-18

## Contexto

O rodapé de toda página dizia *"extraído em 03/09/2026 17:41 UTC"*. Esse valor é
`max(_extracted_at)` de `dim_candidato` — e a tabela tem **um único carimbo**,
reescrito inteiro a cada ingestão.

Consequência: a data mudava todo dia, em toda ficha, mesmo quando nada naquela
candidatura tinha mudado.

### Isso é ruim por dois motivos independentes

**Informa a coisa errada.** O leitor que abre a ficha de um candidato quer saber
a idade *daquele* dado. A data dizia quando a máquina rodou. Uma candidatura que
não muda desde 27/08 exibia "extraído em 03/09" — verdadeiro sobre o processo,
enganoso sobre o dado.

**Faz todo o site mudar todo dia.** Medido em 03/09/2026, com o snapshot
`snap_candidatura_2026`:

| | |
|---|---|
| candidaturas que mudam por dia | ~900 a 1.300 de 20.765 (**~5%**) |
| páginas que mudavam por dia | **100%** |

Duas gerações consecutivas sem reingestão produzem 1.011 arquivos idênticos — o
único diferente é o carimbo de publicação. Ou seja: a única coisa que fazia o
site inteiro mudar era a data global no rodapé.

Isso bloqueava o envio incremental, que é o pré-requisito declarado da F-18. Com
20.765 fichas e 100% de mudança diária, a publicação passaria de ~7 minutos para
~2,5 horas.

## Decisão

A ficha e a página de plano passam a mostrar **quando aquela candidatura mudou
pela última vez**, vindo de `dbt_valid_from` da versão vigente no snapshot:

> Fonte: TSE — Divulgação de Candidaturas · **dados desta candidatura como o TSE
> publicava em 27/08/2026**

Home, listagens e metodologia continuam com a data do site — ali a pergunta é
mesmo "quando isto rodou".

A distribuição real, medida no dia da mudança:

| última mudança | candidaturas |
|---|---|
| 27/08 | 12.729 |
| 31/08 | 4.576 |
| 01/09 | 1.224 |
| 02/09 | 890 |
| 03/09 | 1.183 |

## O que isso preserva

A Constituição §0.3 exige **fonte e data de extração em toda visualização**. As
duas continuam lá; o que mudou é que a data passou a ser a do dado, que é a
leitura mais fiel da própria regra.

Sem o snapshot, a ficha cai na data do site: menos precisa, nunca ausente.

## Consequências

- **~5% das páginas mudam por dia** em vez de 100%. É o que torna o envio
  incremental — e portanto a F-18 — viável.
- Uma ficha parada há uma semana passa a dizer isso, em vez de fingir frescor.
