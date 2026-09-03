# Validação dos indicadores contra fonte oficial

**Última rodada: 01/09/2026.** Regra 6 do CLAUDE.md aplicada ao catálogo inteiro:
cada indicador conferido contra um número **publicado fora do pipeline**.

> `verificado` no catálogo significa "a chamada da API já foi conferida". Não é a
> mesma coisa que o valor bater com o número publicado. Este documento é a segunda
> coisa.

## Resumo

| | |
|---|---|
| Confere com a fonte oficial | **15** de 17 |
| Série oficial diferente da mais divulgada, agora nomeada na tela | **1** (rendimento) |
| Corrigidos por causa da conferência | **2** (desocupação e receita estadual) |

> A primeira versão deste documento somou 14 quando a tabela tinha 13 linhas — a
> desocupação ainda divergia. Hoje são 14 de verdade, com ela corrigida. A
> contagem é conferida contra o catálogo, não digitada à mão.

**Uma série foi trocada por causa desta conferência** (ADR-030): a desocupação
passou da tabela trimestral para a série anual oficial e hoje confere ano a ano.

## Confere

| Indicador | Ano | No lake | Publicado | Fonte conferida |
|---|---|---|---|---|
| IPCA | 2022 | 5,79% | 5,79% | IBGE |
| IPCA | 2023 | 4,62% | 4,62% | IBGE |
| IPCA | 2024 | 4,83% | 4,83% | IBGE |
| SELIC | 2023 | 13,0282% | 13,0282% | **Banco Central, SGS 4390** (acumulada no ano) |
| SELIC | 2024 | 10,8881% | 10,8881% | Banco Central, SGS 4390 |
| PIB | 2023 | R$ 10,943 tri | R$ 10,9 tri | IBGE — Contas Nacionais |
| PIB_PER_CAPITA | 2022 | R$ 49.634 | R$ 49.638,29 | IBGE (0,01% — precisão da população) |
| POPULACAO | 2024 | 212.583.750 | 212.583.750 | IBGE — estimativa do DOU |
| POPULACAO_CENSO | 2022 | 203.080.756 | 203.080.756 | IBGE — Censo 2022 |
| IDEB | série 2005–2025 | 3,2 … 5,0 | idêntica | **planilha oficial do INEP**, linha `Brasil / Pública` |
| MORTALIDADE_INFANTIL | 2016 | 13,3‰ | 13,3‰ | IBGE — SIDRA 3834 |
| IDHM | 2010 | 0,727 | 0,727 | IPEA/PNUD — Atlas do Desenvolvimento Humano |
| RECEITA_LIQUIDA_UNIAO | 2023/2024 | 1,901 / 2,162 tri | idêntico | **planilha do Tesouro Transparente** |
| DESPESA_PRIMARIA_UNIAO | 2023/2024 | 2,130 / 2,205 tri | idêntico | planilha do Tesouro Transparente |
| RESULTADO_PRIMARIO_UNIAO | 2023 | −R$ 228.499.381.293 | −R$ 228,499 bi | Tesouro Nacional |
| RESULTADO_PRIMARIO_UNIAO | 2024 | −R$ 42.923.691.541 | −R$ 43 bi | Tesouro Nacional |
| HOMICIDIOS | 2019–2024 | 22,0 … 20,1 | idêntico | **API do Ipeadata**, série `AVIOL12_THOMIC` |
| DESOCUPACAO | 2022–2025 | 9,6 / 7,7 / 6,6 / 5,6 | idêntico | IBGE — SIDRA t/4562 (anual), desde ADR-030 |
| RECEITA_ESTADUAL | SP/MG/GO 2023, MG 2019 | 229,66 / 92,08 / 38,41 / 64,07 bi | idêntico ao centavo | **RREO Anexo 3** (Receita Corrente Líquida), desde ADR-035 |

### Três armadilhas que a conferência atravessou

**O IDEB de 2021 parece erro e não é.** A série sobe monotonicamente até 2019
(4,6), salta para 4,9 em 2021 e **cai** para 4,7 em 2023. A planilha do INEP
confirma os três. A pandemia inflou o indicador de fluxo em 2021 — foi por isso
que o próprio INEP comparou 2023 com **2019**, e não com 2021.

**O resultado primário de 2023 tem dois números oficiais.** O release do Tesouro
de janeiro/2024 anunciou déficit de R$ 230,535 bi; a série revisada diz
R$ 228,499 bi. O lake tem o revisado, que é o que a planilha atual publica.
Também não é o "R$ 11 bi" de 2024 que saiu nas manchetes: aquele exclui os gastos
extraordinários do Rio Grande do Sul que o arcabouço permite excluir. O nosso é o
resultado cheio, e a metodologia do site já diz isso.

**Os homicídios têm dois números do próprio IPEA.** O Atlas da Violência 2025
publica 21,7 (2022) e 21,2 (2023); a série `AVIOL12_THOMIC` do Ipeadata, que é a
nossa, traz 22,1 e 21,7. Não é ano trocado — é **denominador**: o comentário da
série diz que ela usa população da PNAD Contínua (tabelas 6407 e 6706), e o Atlas
usa outra base. A defasagem é constante (~0,4–0,5 pontos), não um deslocamento.

## Série oficial diferente da mais divulgada

### DESOCUPACAO — ~~diverge~~ **resolvido em 01/09/2026 (ADR-030)**

Vinha da tabela **trimestral** 4099, com o ano formado pela média simples dos
quatro trimestres. Isso produzia um número que **não existia em publicação
nenhuma do IBGE**:

| Ano | Antes (média dos trimestres) | IBGE publica | Agora |
|---|---|---|---|
| 2022 | — | 9,6% | **9,6%** |
| 2023 | 7,98% | 7,7% | **7,7%** |
| 2024 | 6,85% | **6,6%** | **6,6%** |
| 2025 | — | 5,6% | **5,6%** |

Passou a vir da **tabela 4562**, anual na origem (2012–2025), com Brasil e as 27
UFs. Não há mais agregação a fazer.

### RENDIMENTO_MEDIO — série oficial diferente da mais citada

| Ano | No lake | IBGE divulga |
|---|---|---|
| 2024 | R$ 3.492 | **R$ 3.225** |

Duas séries oficiais distintas. A tabela 4566 / variável 5935 é o rendimento
**efetivamente recebido**; o número das manchetes é o **habitualmente recebido**.
Some-se a isso a base de deflação, que a unidade "R$ constantes" não informa.

O valor é fiel à fonte, mas o rótulo do site ("Rendimento do trabalho — quanto
ganha por mês, em média, quem está ocupado, já descontada a inflação") não
distingue as duas coisas.

**Decidido em 01/09/2026 (ADR-030):** mantém-se o **efetivamente recebido**, e a
tela passa a nomear a série. A ficha e a metodologia agora dizem qual das duas é.

Documentado junto, porque a unidade "R$ constantes" escondia: **a base de
deflação anda**. A série real é expressa a preços do período mais recente da
pesquisa, então o valor de um ano passado muda a cada nova divulgação — 2024 vale
R$ 3.492 na série que termina em 2025 e valia outro número antes. Não é revisão
do dado, é troca de base. A variação entre dois anos continua válida; o valor
absoluto não deve ser citado sem a data de extração ao lado.

## O trio do SICONFI — conferido, e corrigido

**Conferido em 03/09/2026 — e o resultado foi encontrar um erro.**

A conferência não achou um número publicado contra o qual comparar o agregado (o
SICONFI não divulga consolidado estadual). Foi então à **estrutura** do dado, e
ali estava o problema:

`RECEITA_ESTADUAL` subtraía FUNDEB e "Outras Deduções", mas **não** as
**Deduções - Transferências Constitucionais** — a parcela do ICMS e do IPVA que
pertence aos municípios por Constituição. Em Minas Gerais, 2023, eram
**R$ 23,8 bilhões** contados como receita do estado, e o `RESULTADO_ORCAMENTARIO`
publicava um **superávit de R$ 24 bilhões num estado em Regime de Recuperação
Fiscal**.

E o problema era maior que a dedução faltante: **a declaração muda**. Em 2023, 22
dos 27 estados declaram transferências constitucionais e 5 não; São Paulo não
declarava dedução nenhuma em 2015 e 2019 e declarava FUNDEB em 2023. A razão
dedução/bruta ia de 7,9% (DF, que não tem municípios a quem repassar) a 37,8%
(MT). A variação publicada na ficha de governador tinha saltos artificiais.

**Correção (ADR-035):** a receita passou a ser a **Receita Corrente Líquida** do
RREO Anexo 3 — definida pela Lei de Responsabilidade Fiscal, obrigatória e
padronizada, cobrindo 2015–2025 nos 27 entes. `DESPESA_ESTADUAL` ficou como
estava: é uma linha única, sempre declarada, sem o problema.
`RESULTADO_ORCAMENTARIO` **saiu** — ver L-26.

## Como refazer

Os valores conferidos saem de:

```
select cod_indicador, ano, valor from marts.fct_indicador_uf_ano where sg_uf = 'BR'
```

As fontes conferidas foram, sempre que possível, o **arquivo primário** que o
próprio pipeline baixou (planilha do INEP, planilha do Tesouro) ou a **API da
instituição** (Banco Central SGS, SIDRA, Ipeadata) — e não notícia sobre o dado.
