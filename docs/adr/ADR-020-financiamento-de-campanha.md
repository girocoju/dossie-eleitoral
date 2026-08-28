# ADR-020 — Financiamento de campanha, com o CPF do doador fora

**Status:** Proposta · **Data:** 2026-08-28 · **Feature:** F-17 (S20)

## Contexto

A prestação de contas eleitoral é o dado que mais aproxima uma candidatura de
quem a sustenta. O TSE publica em massa, e a cobertura de 2026 já é substantiva:

| | |
|---|---|
| Lançamentos de receita | **43.610** |
| Candidaturas com receita declarada | **7.722** |
| Valor declarado | **R$ 3,59 bilhões** |
| Doadores pessoa física | 28.014 lançamentos |
| Doadores pessoa jurídica | 14.292 lançamentos |

Origem dos recursos:

| Origem | Lançamentos |
|---|---|
| Recursos de pessoas físicas | 21.377 |
| Recursos de partido político | 12.497 |
| Recursos próprios | 6.527 |
| Financiamento coletivo | 1.410 |
| **Recursos de outros candidatos** | **373** |

Essa última linha é a mais interessante: o arquivo traz `SQ_CANDIDATO_DOADOR`, o
que permite ligar candidatura a candidatura. É rede de financiamento, não só lista.

## O problema

O arquivo traz **`NR_CPF_CNPJ_DOADOR` em texto puro**. Conferido no primeiro
registro de `receitas_candidatos_2026_AM.csv`:

```
NM_DOADOR              LUIZ CASTRO ANDRADE NETO
NR_CPF_CNPJ_DOADOR     07396570204          ← CPF de pessoa física, legível
```

O doador é público por lei eleitoral — é essa publicidade que permite fiscalizar
quem financia quem. **O CPF dele não precisa ser.** O nome cumpre a função de
prestação de contas; o número só acrescenta risco.

E a Constituição §0.7 do projeto não abre exceção por origem do dado: *não expor
CPF*. Ela vale para candidato e vale para doador — aliás, com mais razão para o
doador, que não se candidatou a nada.

## Decisão

Ingerir o financiamento, com três regras:

**1. CPF de pessoa física nunca é persistido.** Passa pelo mesmo `cpf_hash`
(HMAC-SHA256 com salt) que já usamos para candidato. O hash permite agrupar
doações da mesma pessoa sem guardar o número — que é exatamente o que a análise
precisa e o que a exposição não precisa.

**2. CNPJ fica em claro.** Não é dado pessoal: identifica empresa, partido ou
comitê, e é o que permite rastrear doador institucional. Tratar CNPJ como CPF
seria confundir privacidade de pessoa com opacidade de empresa.

**3. Nome do doador fica.** É a informação de prestação de contas. Sem ela, o dado
não serve para nada — e ela já é publicada pelo TSE exatamente com esse propósito.

## O que a tela precisa dizer, e que o próprio TSE não diz bem

A página do TSE mostra, para o candidato a Presidente com maior campanha do país:

```
Receitas   R$ 35.267.670,96
Despesas   R$ 0,00
```

**"Despesa zero" não significa que não houve gasto.** Significa que a prestação
ainda não foi entregue — o prazo é posterior à eleição. Publicar esse zero sem
contexto sugeriria austeridade onde há apenas ausência de declaração.

É o mesmo erro da distinção "não apresentou plano" × "não é exigido plano", que a
ADR-013 acertou. A tela vai distinguir três estados, sempre:

| Estado | O que aparece |
|---|---|
| Declarou | o valor |
| Prazo aberto, nada entregue | *"prestação ainda não entregue"* |
| Não se aplica | ausência explicada |

## Consequências

**Cobertura hoje é parcial e vai crescer.** 7.722 candidaturas de 20.765 têm
receita declarada — a prestação final vem depois de 04/10. O número na tela precisa
sempre vir com a data de extração, como todo o resto do projeto.

**Doação de candidato a candidato vira dado de rede.** 373 lançamentos já ligam
candidaturas entre si. É o material mais analítico do pacote e não existe pronto em
lugar nenhum de forma consultável.

**Nenhum ranking de "quem arrecadou mais".** Volume de arrecadação não é mérito nem
demérito, e uma lista ordenada por dinheiro é exatamente o tipo de placar que a
Constituição §0.1 proíbe. O valor aparece na ficha de cada um, com comparador de
limite legal ao lado — nunca como classificação.

## Alternativa descartada

**Omitir o doador inteiro** e publicar só totais por origem. Seria mais seguro e
menos útil: o ponto da prestação de contas é justamente saber *quem* financia. O
risco real está no CPF, e o CPF sai — não o nome.
