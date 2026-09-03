# ADR-036 — Publicar não sobrescreve conteúdo mais novo

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** ADR-022, ADR-026, ADR-027

## O incidente

Em 03/09/2026 a página de metodologia foi corrigida — a conferência do SICONFI
(ADR-035) tinha achado um erro de R$ 24 bilhões, e o texto que dizia *"isso não
foi feito"* sobre aquela conferência ficou falso no mesmo instante.

A correção foi publicada às 01:41 e **conferida no ar**. Depois:

| hora | o que aconteceu |
|---|---|
| 01:41 | publicação manual, com a metodologia corrigida — conferida |
| 02:54 | execução do CI do commit `482a527` **republicou por cima**, com a metodologia antiga |
| 05:38 | execução do commit correto **falhou** na ingestão e pulou a publicação |

O site ficou afirmando que uma conferência não tinha sido feita, no dia em que
ela foi feita e achou o erro. Só foi notado porque o dono do projeto perguntou
"ajustou a metodologia no site?".

## As duas causas

**1. Publicamos de dois lugares.** A publicação manual sai da árvore de trabalho;
o `git push` dispara o workflow, que gera do commit dele e publica também. Uma
execução iniciada antes pode terminar depois e vencer.

**2. O critério intuitivo — horário — está errado.** A execução do CI era a mais
recente no relógio (02:54 contra 01:41) e a mais **velha** no conteúdo: ela vinha
de um commit anterior. Ordenar por tempo teria deixado passar exatamente este
caso.

## Decisão

O site passa a carregar um carimbo, `.publicacao.json`, com `gerado_em`, o
`commit` de origem e se a árvore estava suja. `scripts/publicar.py` lê o carimbo
que está no servidor **antes de enviar** e recusa quando o commit local é
**ancestral** do commit publicado.

O critério é linhagem, não horário.

```
RECUSADO: este site vem de 482a527, que e' ANCESTRAL de bcaf1e1,
ja' publicado em 2026-09-03T04:41:00+00:00. Publicar sobrescreveria
conteudo mais novo com conteudo mais velho.
```

### Três casos que a regra precisa deixar passar

**Árvore suja nunca é bloqueada.** Conteúdo publicado à mão não está em commit
nenhum; tratá-lo como "antigo" bloquearia justamente a correção urgente — que foi
o que aconteceu neste incidente.

**Commit desconhecido não trava.** Um clone raso pode não conhecer o commit
remoto. Aí o publicador **avisa e publica**: travar a publicação por não saber
comparar seria pior que o risco que a regra evita.

**Rollback deliberado tem saída.** `--forcar` existe para quando sobrescrever com
conteúdo anterior é mesmo o que se quer.

## O que NÃO foi feito, e por quê

Tirar o gatilho de `push` do workflow removeria a corrida por construção, e foi
considerado. Mas o workflow é a rede de segurança para quando a máquina do
usuário está desligada (ADR-026), e desligá-lo trocaria uma falha rara e agora
detectável por uma indisponibilidade silenciosa. O guarda protege sem tirar a
rede.

## Consequências

- Toda publicação passa a ler um arquivo do servidor antes de enviar. Custa uma
  requisição.
- Uma execução do CI atrasada agora **falha alto** em vez de regredir o site em
  silêncio.
- O carimbo também serve de diagnóstico: dá para saber de qual commit veio o que
  está no ar.
