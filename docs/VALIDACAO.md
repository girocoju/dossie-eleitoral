# Validação dos indicadores contra fonte oficial

**Última rodada: 01/09/2026.** Regra 6 do CLAUDE.md aplicada ao catálogo inteiro:
cada indicador conferido contra um número **publicado fora do pipeline**.

> `verificado` no catálogo significa "a chamada da API já foi conferida". Não é a
> mesma coisa que o valor bater com o número publicado. Este documento é a segunda
> coisa.

## Resumo

| | |
|---|---|
| Confere com a fonte oficial | **14** de 18 |
| Diverge do número mais divulgado, por motivo identificado | **2** |
| Não validado contra publicação externa | **3** (trio SICONFI) |

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

## Diverge do número mais divulgado

### DESOCUPACAO — o site mostra número diferente do que o IBGE publica

| Ano | No lake | IBGE publica |
|---|---|---|
| 2023 | 7,98% | **7,8%** |
| 2024 | 6,85% | **6,6%** |

O valor anual é a **média simples dos quatro trimestres** (declarado em
`agregacao: media_anual`). O IBGE calcula a taxa anual a partir da amostra anual
agrupada, não pela média dos trimestres — e os dois não coincidem.

Não é erro de extração: é escolha de agregação que produz um número que **não
existe em publicação nenhuma do IBGE**. Quem conferir vai achar 6,6% e ler 6,85%
no site.

**Pendente de decisão:** trocar pela série anual oficial do IBGE.

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

**Pendente de decisão:** dizer "efetivamente recebido" no rótulo e a base de
deflação, ou trocar para a série habitual.

## Não validado contra publicação externa

`RECEITA_ESTADUAL`, `DESPESA_ESTADUAL` e `RESULTADO_ORCAMENTARIO` no nível
Brasil são a **soma dos 27 estados feita por este projeto** — o SICONFI não
publica consolidado estadual, como o próprio `fct_indicador_uf_ano` registra.
Não há número publicado contra o qual comparar o agregado.

Validar isso exige conferir **um estado por vez** contra o Balanço Geral daquele
estado. Não foi feito. Fica registrado como pendência, e não como "conferido".

## Como refazer

Os valores conferidos saem de:

```
select cod_indicador, ano, valor from marts.fct_indicador_uf_ano where sg_uf = 'BR'
```

As fontes conferidas foram, sempre que possível, o **arquivo primário** que o
próprio pipeline baixou (planilha do INEP, planilha do Tesouro) ou a **API da
instituição** (Banco Central SGS, SIDRA, Ipeadata) — e não notícia sobre o dado.
