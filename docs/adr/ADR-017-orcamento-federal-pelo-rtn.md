# ADR-017 — Orçamento federal vem do RTN, não da DCA

**Status:** Aceita · **Data:** 2026-08-28 · **Feature:** F-04 (S18) · **Fecha:** L-22

## Contexto

O projeto media o orçamento federal com a mesma fonte dos estados: a Declaração de
Contas Anuais (DCA) do SICONFI. Parecia elegante — uma fonte, uma conta, dois
níveis de governo.

Estava errado, e o erro sobreviveu a `dbt build` verde, a 205 testes e a uma
revisão de código. Só apareceu quando um número foi conferido **contra a
realidade**, ao gerar insights de exemplo:

| Ano | Série do projeto | Resultado primário real |
|---|---|---|
| 2020 | **−48 bi** | **−743 bi** |
| 2025 | **+635 bi** (superávit) | **−61,7 bi** (déficit) |

## Causa

Medido no anexo I-C da União de 2020:

```
TOTAL DAS RECEITAS                   R$ 3.754,5 bi
  Receitas de Capital                R$ 2.135,6 bi
    Operações de Crédito             R$ 1.647,9 bi   ← 45% do total
  Receitas Correntes                 R$ 1.586,4 bi
```

**Operações de crédito são dívida emitida**, e a DCA as classifica como receita —
corretamente, do ponto de vista orçamentário: o orçamento fecha por construção,
porque o financiamento do déficit entra do lado da receita. Receita menos despesa
tende a zero por **identidade contábil**, não por equilíbrio fiscal.

O número estava certo. Errado era o **rótulo**.

### Por que os estados não têm o problema

Operações de crédito como fração da receita, em 2023:

| SP | RJ | MA |
|---|---|---|
| 1,1% | 0,1% | 0,2% |

A distorção é específica de um ente que se financia por dívida em escala federal.
`RECEITA_ESTADUAL`, `DESPESA_ESTADUAL` e `RESULTADO_ORCAMENTARIO` continuam vindo
do SICONFI, e continuam válidos.

## Decisão

O orçamento federal passa a vir do **Resultado do Tesouro Nacional (RTN)**, tabela
2.1 da série histórica, substituindo as três séries antigas:

| Removido (DCA) | Novo (RTN) |
|---|---|
| `RECEITA_UNIAO` | `RECEITA_LIQUIDA_UNIAO` |
| `DESPESA_UNIAO` | `DESPESA_PRIMARIA_UNIAO` |
| `RESULTADO_ORCAMENTARIO_UNIAO` | `RESULTADO_PRIMARIO_UNIAO` |

Das três saídas registradas na L-22 — excluir operações de crédito, usar só
receitas correntes, ou trocar de fonte — esta é a única que entrega **o conceito
que o leitor já tem na cabeça** ao ler "déficit". Numa tela pública, esse é o teste
que importa: um número tecnicamente extraível mas que ninguém interpreta como o
autor pretendia é um número errado.

Ganho colateral: a série vai de **1997**, contra 2015 da DCA. Cobre sete mandatos
presidenciais em vez de dois.

### Conferência

| Ano | `RESULTADO_PRIMARIO_UNIAO` | Verificação |
|---|---|---|
| 2020 | −743,3 bi | bate com o déficit do ano da pandemia |
| 2022 | **+46,4 bi** | superávit, corretamente positivo |
| 2023 | −228,5 bi | bate com o resultado divulgado |

Uma série que só produz déficit não teria como ser conferida; 2022 dar superávit é
o que mostra que o sinal está certo.

## Detalhes de implementação que viram armadilha

**A URL muda todo mês.** O arquivo se chama `seriehistoricajul26.xlsx` e vira
`ago`, `set`… A URL é resolvida a cada execução pela API CKAN do Tesouro
Transparente, pelo id estável do conjunto. Fixar o nome quebraria a carga em algum
dia de setembro, sem ninguém entender por quê.

**A rubrica é casada por prefixo numerado.** O Tesouro mantém `5. RESULTADO
PRIMÁRIO GOVERNO CENTRAL` e mexe no sufixo (notas de rodapé mudam de `1/` para
`2/` entre edições). Casar por prefixo é estável; casar pelo rótulo inteiro
quebraria na próxima revisão. Se o prefixo casar com **mais de uma linha**, a carga
**falha** em vez de escolher — duas linhas parecidas se sobrescreveriam sem aviso.

**"Acima da linha", não "abaixo".** A tabela traz as duas medições, que diferem por
ajustes metodológicos e discrepância estatística. São poucos bilhões, mas misturar
as duas entre anos criaria degraus falsos numa série de 29 anos.

## O que esta série não é

Não é o resultado do **setor público consolidado** (que inclui estados, municípios
e estatais) nem o resultado **nominal** (que inclui juros da dívida — R$ 892 bi só
em 2025). É o Governo Central, primário: o nível de governo e o conceito pelos
quais um presidente responde.

E, como PIB e Selic, descreve o **período**, não o efeito de um mandato
(Constituição §0.2).

## Lição que fica

Nenhum teste automático pegaria isso. O dado era extraído corretamente, a fonte era
oficial, o teste de relacionamento passava, o comparador existia. O que faltava era
**conferir um número contra o mundo** — e foi só isso que revelou o erro.

Vale como regra para as próximas séries: antes de publicar um indicador, comparar
ao menos um ano com um valor conhecido de fora do pipeline.
