# ADR-037 — O site remove do servidor o que não gera mais

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** ADR-027, ADR-036, L-23

## Contexto

O gerador **não limpa o diretório de saída**. Ele escreve as páginas por cima do
que já estava lá, e o publicador envia tudo que encontra. Consequência: uma
página gerada uma vez fica publicada para sempre, mesmo quando o site deixa de
gerá-la.

Medido em 03/09/2026, seis páginas vivas no ar:

| URL | o que era |
|---|---|
| `/candidato/helio-bolsonaro-230002534806/` | nome de urna que o TSE **não registra mais** |
| `/candidato/nilton-santos-270002550610/` | idem — hoje é "CORONEL NILTON SANTOS" |
| `/candidato/hermano-morais-200002535256/` | idem — hoje é "HERMANO" |
| `/candidato/guto-schiavetto-250002554075/` | `e_registro_exibido = false` |
| `/candidato/sargento-laudicerio-110002554073/` (+ plano) | `e_registro_exibido = false` |

Os três primeiros são o caso mais grave: a pessoa mudou o nome de urna, a ficha
atual foi para outra URL, e a antiga **congelou no dia da mudança** — publicada,
indexável e sem nada que a desminta. Os dois últimos são candidaturas com
registro duplicado que o projeto decidiu **não** mostrar, e que continuavam no ar.

São seis hoje. Com a campanha em curso — nome de urna muda, registro é
indeferido, candidatura é retirada (L-23) — e com a F-18 levando o site a 21 mil
páginas, isso vira dezenas de fichas desatualizadas de pessoas reais.

## Decisão

O publicador passa a manter um **manifesto no servidor** (`.arquivos.json`) com
tudo que deixou lá. Na publicação seguinte ele compara: o que estava no manifesto
e não está no site atual é removido.

### Por que manifesto e não varredura

Descobrir órfãs varrendo a árvore remota custa **uma listagem por diretório**, e
cada candidato tem o seu: mil hoje, vinte e uma mil com a F-18. O manifesto é um
arquivo só.

A varredura existe como caminho de exceção — primeira publicação com a limpeza
ligada, ou manifesto apagado.

### A ordem importa, e por dois motivos

1. O manifesto anterior é lido **antes** do envio: subir o novo sobrescreve o
   antigo, e sem ele não há como saber o que virou órfão.
2. A remoção acontece **depois** do envio: se viesse antes e o envio falhasse, o
   site ficaria sem as páginas novas *e* sem as antigas.

## As proteções, e o que cada uma evita

**Teto de 25%, com piso de 20 arquivos.** Uma geração truncada produz poucos
arquivos, e sem teto a limpeza apagaria o site inteiro achando que tudo virou
órfão. O piso existe porque percentual sozinho é agressivo demais em número
pequeno: uma órfã num site de duas páginas já é 50%. Acima do teto, `--forcar`.

**Só remove o que estava no manifesto.** Arquivo que alguém pôs no servidor à mão
nunca esteve lá e não é tocado.

**Varredura incompleta não dirige remoção.** A conexão TLS cai no meio da
listagem — `SSL: BAD_LENGTH`, a mesma instabilidade do ADR-027 — e uma varredura
que morre devolve **menos** arquivos, o que se parece com um inventário limpo.
Duas execuções seguidas devolveram 144 e 302 de ~1.019. A varredura agora
reporta se terminou, e um inventário parcial é recusado: deletar com base no que
não foi visto é como a limpeza destruiria conteúdo.

**Pasta vazia sai junto.** Apagar só o `index.html` deixa o diretório, e o
servidor responde **403** em vez de 404 — pior para quem chega por link antigo,
porque "proibido" sugere que existe algo ali. `RMD` recusa diretório não-vazio,
então isso nunca leva conteúdo junto.

## As seis de hoje

Foram removidas à mão, com verificação prévia de que nenhuma é gerada pelo site
atual, porque elas nunca estiveram em manifesto nenhum — e a varredura, que as
pegaria, não completa por causa da queda de conexão. As URLs antigas agora
respondem 404 e as fichas atuais das mesmas pessoas seguem no ar.

## Consequências

- Toda publicação lê e escreve um arquivo a mais. Custa duas requisições.
- Uma ficha que muda de URL deixa de ter duas versões vivas.
- É pré-requisito da F-18: com 21 mil páginas, o acúmulo seria muito maior.
