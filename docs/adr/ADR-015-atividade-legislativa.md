# ADR-015 — Como medir atividade legislativa sem produzir um placar

**Status:** Aceita · **Data:** 2026-08-28 · **Feature:** F-16

## Contexto

A ficha de um deputado precisa mostrar o que ele **fez** no mandato. O número que
circula na imprensa e nos rankings de ONGs é "quantas proposições o deputado
apresentou". Esse número é enganoso por três motivos independentes, e cada um foi
medido nesta base antes de qualquer decisão de modelagem.

## O que a medição mostrou (2025, arquivo completo da Câmara)

| Problema | Medição |
|---|---|
| Assinatura contada como autoria | 139.413 linhas de autoria com deputado; **21,4% são apoio, não proposta**. O maior requerimento do ano tem **264 assinaturas**, das quais 263 são apoio |
| Tipos somados como se fossem a mesma coisa | 7.695 projetos de lei · 31.479 requerimentos de retirada de pauta · 15.501 pareceres de relator |
| Destino ausente | 58.385 proposições (53%) vêm com **situação em branco** na fonte |

Um "ranking de produtividade" construído sobre isso premia quem assina tudo e
quem protocola requerimento de rito.

## Decisão

Três filtros, todos declarados no dado e não em comentário:

1. **`proponente = 1`.** Assinatura de apoio nunca entra. `total_assinantes` viaja
   junto na linha, para que um projeto com 1 assinante e outro com 264 não pareçam
   equivalentes.
2. **`classe_proposicao` faz parte do grão** de `fct_atividade_legislativa`. Não
   existe linha "total do deputado": `normativa`, `fiscalizacao`, `relatoria`,
   `procedimental`, `outra`. Somar as classes é possível para quem insistir, mas o
   modelo não oferece a soma pronta.
3. **Destino explícito**, com `qt_destino_desconhecido` separado de
   `qt_em_tramitacao`. Ausência de informação não é andamento.

### O que fica de fora, de propósito

**Taxa de aprovação.** Aprovar depende de estar na base do governo, não do mérito
do texto. Uma taxa puniria a oposição por ser oposição — em qualquer governo, de
qualquer partido. Isso é placar, e viola a Constituição §0.1. Há
`qt_virou_norma` em número absoluto ao lado do total; o leitor tira a conclusão.

**`relatoria` não é autoria.** O deputado não propôs nada, relatou o texto de
outro. É trabalho de peso — 15.501 pareceres em 2025 — e por isso está no modelo,
em classe própria. Somar com projeto de lei confundiria quem escreveu com quem
analisou.

## Fonte: arquivos em bloco, não a API

A API exigiria uma chamada a `/proposicoes/{id}/autores` por proposição para saber
quem é proponente — dezenas de milhares de requisições por ano. Os arquivos anuais
(`proposicoesAutores-{ano}.csv`, `proposicoes-{ano}.csv`) trazem o mesmo em dois
downloads. Custo da legislatura 2023-2026 inteira: 8 arquivos, ~500 MB, uma vez.

## Dois erros que a verificação pegou antes da carga

1. **`virou_norma` dava zero.** A constante estava em `transformada em norma
   jurídica`; a Câmara escreve com o gênero do **tipo** da proposição —
   "Transformad**o** em Norma Jurídica" para um projeto de lei. Um painel afirmando
   que nenhum projeto virou lei é pior do que um painel sem o campo. Passou a casar
   por trecho, sem gênero.

2. **`outra` era a maior classe** (57.907 de 109.582 em 2025), porque `PRL`
   (parecer de relator) e `RPD` (retirada de pauta) não estavam mapeados. Depois da
   correção: 5,8%. O teste `assert_classe_proposicao_reconhecida` falha se voltar a
   passar de 15% — é o que detecta a Câmara criando um tipo novo de alto volume.

## Consequência

`fct_atividade_legislativa`: 9,1 mil linhas, 296.962 proposições de 710 deputados
(710 > 513 por causa de suplências e licenças ao longo de quatro anos). 511
deputados ligados ao TSE por `id_pessoa`; os demais são quem já saiu do exercício,
e a linha deles fica marcada com `ligado_ao_tse = false` em vez de ser descartada.
