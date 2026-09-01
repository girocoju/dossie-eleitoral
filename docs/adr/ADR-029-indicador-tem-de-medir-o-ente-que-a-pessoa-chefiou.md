# ADR-029 — O indicador tem de medir o ente que a pessoa chefiou

**Status:** Aceita · **Data:** 2026-08-31 · **Relacionada:** ADR-028, ADR-023, ADR-017 (L-22), F-06

## Contexto

A ficha do Lula — presidente — trazia duas linhas assim:

| Indicador | Janela | Variação | Brasil no mesmo período |
|---|---|---|---|
| Despesa do estado | 2022–2025 | +38,2% | +38,2% |
| PIB do estado | 2022–2023 | +8,6% | +8,6% |

Três coisas erradas na mesma tabela.

**1. O número não era dele.** `fct_indicador_uf_ano` cria uma linha `sg_uf = 'BR'`
para o orçamento **estadual** somando os 27 estados. O próprio modelo diz para
que ela serve: é o **comparador** de um governador — quanto o conjunto dos
estados arrecadou e gastou. Como a ficha de um presidente tem `nm_ue = BRASIL`,
essa linha entrava como se fosse o orçamento dele. Medido em 31/08/2026: **9
linhas em 4 fichas presidenciais.**

**2. O rótulo dizia "estado" para um número nacional.** "PIB do estado" na ficha
de quem governou o país. É a família de erro do ADR-023 e da L-22: o dado certo,
o **rótulo** afirmando algo falso. Nenhum teste pega — cada célula está correta.

**3. A coluna de comparação comparava o Brasil com o Brasil.** Num mandato
nacional o indicador **é** o Brasil, então "Brasil no mesmo período" repetia o
mesmo número: **76 das 78 linhas** presidenciais tinham as duas variações
idênticas, e as outras 2 não tinham comparador nenhum.

Como consulta pública, cada uma dessas três coisas custa confiança de quem lê.

## Decisão

### O catálogo passa a declarar o que cada indicador mede

Campo novo `ente_medido` em `ingest/layouts/indicadores.yml`, que vai para
`dim_indicador`:

| Valor | O que mede | Onde pode aparecer |
|---|---|---|
| `territorio` | o território governado — PIB, população, homicídios, IDEB… | qualquer cargo; **o rótulo é que muda** |
| `governo_estadual` | o orçamento do governo do estado | só ficha de governador |
| `governo_federal` | o orçamento do governo federal | só ficha de presidente |
| `economia_nacional` | IPCA, Selic | só mandato nacional |

`economia_nacional` não é `governo_federal` de propósito: a Selic é definida pelo
Copom, que é independente. Guardar as duas no mesmo balde já seria atribuição, e
a Constituição §0.2 proíbe (correlação não é causalidade).

Antes, o escopo era acidental: IPCA e Selic não apareciam em ficha de governador
apenas porque não existem linhas por UF. Funcionava por acidente, e acidente não
protege — o orçamento estadual, que **tem** linha `BR`, passava.

### `fct_mandato_indicador` filtra por ente × cargo

A regra vive no dbt, não na tela: "este indicador não se aplica a este cargo" é
afirmação sobre o dado, não sobre a apresentação.

### O rótulo segue o ente governado

"PIB do Brasil" na ficha presidencial, "PIB do estado" na de governador, "PIB" no
catálogo da metodologia — que fala dos dois casos ao mesmo tempo. O mesmo para a
explicação da população ("moram no país" / "moram no estado").

### Mandato nacional não mostra a coluna "Brasil no mesmo período"

Comparar o Brasil com o Brasil não é comparação: é ruído que parece erro.

## Consequências

- Ficha de presidente perde 9 linhas de orçamento estadual e uma coluna. Fica
  menor e verdadeira.
- Ficha de governador não muda: continua com as quatro colunas e o comparador
  nacional, que ali significa alguma coisa.
- Indicador novo passa a **exigir** a declaração de `ente_medido` — o catálogo
  falha alto se faltar, em vez de deixar o valor escorrer para a ficha errada.
- Falta ao projeto uma medida do orçamento **federal** comparável entre os três
  mandatos do Lula e os de outros presidentes; o RTN cobre isso e já está lá.
  Nenhuma lacuna nova foi criada — apenas se parou de preencher uma com o número
  errado.
