# ADR-035 — A receita estadual passa a ser a Receita Corrente Líquida

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** ADR-017 (L-22), ADR-030, Regra 6, L-26 (nova)

## Contexto

A validação dos indicadores (ADR-030) deixou uma pendência declarada em público:
o trio do SICONFI — receita, despesa e resultado do estado — nunca tinha sido
conferido contra publicação externa, porque no nível Brasil ele é a soma dos 27
estados feita por este projeto e não existe consolidado publicado para comparar.

A conferência foi feita em 03/09/2026. Não achou número externo para o agregado —
e achou um **erro na estrutura**.

## O que estava errado

`RECEITA_ESTADUAL` vinha da DCA: "Receitas Brutas Realizadas" menos as deduções
declaradas. O código conhecia duas deduções — FUNDEB e "Outras" — e **não**
conhecia a terceira: **Deduções - Transferências Constitucionais**, a parcela do
ICMS e do IPVA que pertence aos municípios por Constituição e que o estado nunca
teve para gastar.

Em **Minas Gerais, 2023**, eram **R$ 23,8 bilhões** contados como receita do
estado. O `RESULTADO_ORCAMENTARIO`, que era `receita − despesa`, publicava um
**superávit de R$ 24 bilhões num estado que estava em Regime de Recuperação
Fiscal**. Com a dedução correta, o mesmo ano fica praticamente em equilíbrio.

### E o problema era maior que a dedução faltante

A declaração das deduções **não é padronizada**. Medido em 03/09/2026:

- em 2023, **22 dos 27** estados declaram transferências constitucionais; 5 não;
- **São Paulo** não declara dedução nenhuma em 2015 e 2019, e declara FUNDEB em
  2023 — a variação publicada na ficha tinha um salto artificial de R$ 34 bi;
- a razão dedução/bruta ia de **7,9%** (DF, que não tem municípios a quem
  repassar) a **37,8%** (MT).

Corrigir a dedução faltante consertaria Minas e deixaria São Paulo quebrado. O
indicador não era comparável nem entre estados nem entre anos do mesmo estado — e
a ficha de governador publica exatamente uma variação entre dois anos.

## Decisão

**`RECEITA_ESTADUAL` passa a ser a Receita Corrente Líquida**, do RREO Anexo 3.

A RCL é definida pela Lei de Responsabilidade Fiscal e usada oficialmente para os
limites de pessoal e de dívida. É padronizada por construção: todo ente é
obrigado a publicá-la no mesmo formato. Cobre **2015–2025 nos 27 entes**.

Conferida contra a fonte, ao centavo:

| | lake | RREO oficial |
|---|---|---|
| SP 2023 | 229.658.088.101,43 | idêntico |
| MG 2023 | 92.079.439.352,23 | idêntico |
| GO 2023 | 38.407.128.875,35 | idêntico |
| MG 2019 | 64.068.169.194,30 | idêntico |

**`DESPESA_ESTADUAL` fica como está.** É uma linha única do Anexo I-D, sempre
declarada — conferido em 3 anos × 8 UFs, sem falha. O problema era só da receita.

**`RESULTADO_ORCAMENTARIO` sai.** RCL é receita *corrente*; a despesa é empenhada
*total*, com capital. Subtrair as duas produziria um déficit estrutural que não
existe.

## A alternativa que foi sondada e recusada

O RREO Anexo 6 publica `RESULTADO PRIMÁRIO (COM RPPS)`, padronizado e oficial —
seria o espelho exato do `RESULTADO_PRIMARIO_UNIAO` que já mostramos para o
governo federal, e chegou a parecer a escolha melhor.

Foi recusado por **cobertura**: a conta só aparece a partir de **2023**. Três anos
não cobrem uma janela de mandato de quatro. Registrado como L-26, com o caminho
para fechar: mapear os rótulos do Anexo 6 nas versões antigas do RREO.

Vale registrar que a alternativa parecia melhor até a cobertura ser medida. A
regra do projeto — conferir antes de dar por pronto — funcionou contra a própria
ideia mais bonita.

## Consequências

- Os números de receita de **27 estados em 11 anos** mudam. É mudança de número
  publicado, feita com autorização explícita.
- O bloco fiscal da ficha de governador perde uma linha (o resultado) e ganha uma
  medida comparável.
- A ausência do resultado é **dita na ficha**, pelo mecanismo do ADR-031: a nota
  de rodapé do bloco lista o que falta e por quê.
