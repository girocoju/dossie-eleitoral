# ADR-043 — A situação no TSE ganha cor, e a cor não emite juízo

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** F-25, Constituição §0.1, ADR-018

## Contexto

A ficha mostrava a situação como texto puro: *"AGUARDANDO JULGAMENTO"*,
*"INDEFERIDO EM PRAZO RECURSAL OU COM RECURSO"*. São nove valores em 2026, e
numa listagem de 1.126 nomes ninguém decifra nove rótulos jurídicos.

| situação | candidaturas |
|---|---|
| DEFERIDO | 15.598 |
| AGUARDANDO JULGAMENTO | 4.500 |
| RENÚNCIA | 469 |
| INDEFERIDO EM PRAZO RECURSAL OU COM RECURSO | 147 |
| INDEFERIDO | 93 |
| DEFERIDO EM PRAZO RECURSAL OU COM RECURSO | 23 |
| PEDIDO NÃO CONHECIDO | 4 |
| PENDENTE DE JULGAMENTO | 3 |
| CANCELADO | 1 |

## Decisão

Quatro cores, e cada uma diz **em que ponto do rito o registro está** — que é
fato publicado pelo TSE.

| cor | situações | o que a cor afirma |
|---|---|---|
| **verde** | DEFERIDO | a Justiça Eleitoral aprovou |
| **âmbar** | AGUARDANDO e PENDENTE DE JULGAMENTO, DEFERIDO e INDEFERIDO EM PRAZO RECURSAL | ainda não está decidido |
| **vermelho** | INDEFERIDO, PEDIDO NÃO CONHECIDO, CANCELADO | pedido negado ou cancelado |
| **cinza** | RENÚNCIA | ato do próprio candidato |

## As duas escolhas que importam

**"Em prazo recursal" é âmbar, não verde nem vermelho.** Pintar *"INDEFERIDO EM
PRAZO RECURSAL OU COM RECURSO"* de vermelho afirmaria um desfecho que a fonte não
declara — e seria uma afirmação publicada sobre uma pessoa real. O âmbar diz "a
decisão ainda pode mudar", que é exatamente o que o campo diz.

**Renúncia é cinza, não vermelho.** Renunciar é ato do próprio candidato, não
decisão contra ele. Vermelho ali leria como recusa da Justiça Eleitoral, que não
foi o que aconteceu.

## O limite que a cor não pode passar

Cor é a forma mais rápida de ranquear sem escrever nada, e a Constituição §0.1
proíbe ranquear candidato. Verde aqui significa *"o registro foi deferido"*, nunca
*"este candidato é bom"*. Nenhuma cor de partido entrou junto — o teste
`test_nenhuma_cor_de_partido_entrou_junto` trava as quatro classes permitidas.

## Acessibilidade

O rótulo continua **escrito** ao lado em todos os casos. Cerca de 8% dos homens
têm alguma forma de daltonismo, e verde/vermelho é justamente o par que some: a
cor reforça, quem informa é o texto.

Cada situação traz `title` e `aria-label` com uma frase explicando o que
significa — *"PEDIDO NÃO CONHECIDO"* não diz nada a quem não é do meio jurídico.

## Situação desconhecida não inventa cor

O TSE pode publicar um valor novo. Ele cai em cinza e mantém o rótulo original:
escolher verde ou vermelho por conta própria seria afirmar um desfecho que
ninguém declarou.

## Um mapa só, não dois

A listagem filtrável desenha em JavaScript, e a tentação era escrever a lista de
situações uma segunda vez lá. O mapa do Python é **serializado** para dentro da
página: duas listas escritas à mão divergiriam no dia em que o TSE criasse um
valor novo, e a listagem passaria a pintar diferente da ficha.
