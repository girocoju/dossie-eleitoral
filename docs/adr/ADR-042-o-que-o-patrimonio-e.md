# ADR-042 — De que o patrimônio é feito, e o que a ficha não diz sobre ele

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** F-24, Constituição §0, Regra 5, Regra 6, L-27, ADR-034

## Contexto

A ficha trazia duas linhas sobre patrimônio: **"Total declarado R$ 2.221.000 · Itens 10"**.
Dois patrimônios do mesmo tamanho podem ser uma fazenda ou vinte apartamentos, e
a diferença é justamente o que alguém quer saber. A fonte tem 76.724 itens só em
2026, cada um com tipo oficial e valor, e declarações desde 2006.

## Decisão

Quatro blocos novos na ficha, todos a partir de dados que já estavam no lake:

1. **De que é feito o patrimônio** — por tipo, agrupado, com fatia.
2. **Patrimônio declarado a cada eleição** — as declarações lado a lado.
3. **Mandatos exercidos** — o que a pessoa chegou a exercer.
4. **Está em exercício hoje** — aviso no topo, para 501 candidaturas.

## A descrição do bem não vai à tela — nem ao mart

`ds_bem` é texto livre preenchido pelo candidato. Medido em 03/09/2026 sobre as
76.724 declarações de 2026:

| o que aparece na descrição | linhas | |
|---|---|---|
| endereço (rua, avenida, quadra, CEP, bairro) | 5.218 | 6,8% |
| CNPJ formatado | 1.315 | 1,7% |
| banco, agência ou número de conta | 566 | 0,7% |
| placa de veículo | 455 | 0,6% |
| número de porta | 394 | 0,5% |
| matrícula de imóvel | 217 | 0,3% |
| CPF formatado | 172 | 0,2% |

Um caso real: *"DIREITOS POSSESSÓRIOS DO IMÓVEL RESIDENCIAL NA RUA (…), 145,
AFOGADOS, RECIFE/PE"*. É o **endereço residencial de uma pessoa real**, e a
Constituição §0 proíbe expor endereço de candidato.

A proteção escolhida é estrutural: **o campo não existe em `fct_bem_candidatura`**.
O que não chega ao mart não chega à tela por descuido de quem escrever a próxima
consulta, e não depende de ninguém lembrar da regra.

O **tipo**, sim, vai — ele vem da tabela oficial de códigos, não de texto livre,
e diz "Apartamento" sem dizer qual.

## O agrupamento vem da estrutura oficial, não do nome

`cd_tipo_bem` é a tabela de Bens e Direitos da Receita Federal, que o TSE reusa,
e ela já é organizada por dezena: 01-19 imóveis, 21-29 móveis, 31-39
participações, 41-49 aplicações, 51-59 créditos, 61-69 dinheiro, 71-79 fundos,
91-99 outros.

Classificar pela dezena é ler a estrutura que a fonte declara. Adivinhar pelo
nome seria repetir o erro que a L-20 custou caro: `RQI` parece "Requerimento de
Informação" e é "Requerimento da Comissão de Serviços de Infraestrutura"
(ADR-034).

## A série não calcula variação. Em lugar nenhum.

Não há coluna de variação no mart, nem percentual na tela, nem seta. Três
motivos, e cada um sozinho bastaria:

1. **O TSE pede valor de aquisição**, não de mercado. Um imóvel comprado em 2005
   é declarado pelo preço de 2005 em toda eleição seguinte. A diferença entre
   dois anos mede compra e venda tanto quanto qualquer outra coisa.
2. **Os valores são nominais.** R$ 500 mil em 2022 e R$ 550 mil em 2026 é
   **queda** em termos reais, e um "+10%" afirmaria o contrário.
3. **É declaração do próprio candidato**, não apuração de ninguém.

A tela mostra as declarações e diz as três coisas. Quem quiser concluir algo
conclui com o dado à vista — o site registra, não avalia (Constituição §0.1).

E ano sem declaração **não aparece**: a linha ausente não é patrimônio zero.
Foi por isso que o arquivo de 2006, que publica itens zerados, virou a
[L-27](../LACUNAS.md) em vez de virar uma queda a pico na tela de 6.699 pessoas.

## Conferência (Regra 6)

Contra o **DivulgaCandContas**, que é outro sistema do TSE, com outro formato e
outra rota de publicação — se os dois batem, o erro teria de estar nos dois
lugares ao mesmo tempo:

| | |
|---|---|
| bens 2026, amostra do maior ao menor | **7 de 7 conferem ao centavo** |
| patrimônio 2022, 5 declarações (uma com 180 itens) | **5 de 5 conferem ao centavo** |

Contra a **API da Câmara**, para o "em exercício":

| | |
|---|---|
| deputados que a Câmara lista em exercício | 513 |
| que o pipeline marca em exercício | 513 |
| divergência nos dois sentidos | **0** |

## Consequências

- 12.732 candidaturas proporcionais ganham o detalhe de bens; 4.277 ganham a
  série; 2.006 ganham o bloco de mandatos; 501 ganham o aviso de exercício.
- Ficha sem nenhum desses dados não ganha bloco vazio: peso visual de conteúdo
  onde não há conteúdo sugere que falta alguma coisa.
