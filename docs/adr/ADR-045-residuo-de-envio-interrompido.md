# ADR-045 — Resíduo de envio interrompido não pode matar a publicação

**Status:** Aceita · **Data:** 2026-09-04 · **Relacionada:** ADR-027, ADR-039

## Contexto

O servidor da Hostinger grava cada upload num arquivo oculto `.in.<nome>.` e só
o renomeia no fim. Quando a transferência morre no meio — conexão cortada, ou
alguém parando a publicação — o oculto **fica**. O `STOR` seguinte no mesmo
caminho responde:

```
550 candidato/x/index.html: Temporary hidden file
    /candidato/x/.in.index.html. already exists
```

`550` é `error_perm`, que o publicador trata como erro de verdade e deixa subir
(ADR-027, e com razão: caminho errado e permissão negada também são 550).

Em 04/09/2026 isso matou uma publicação **depois de 6.200 arquivos**, e o resíduo
tinha sido deixado por duas publicações que eu mesmo interrompi mais cedo.

## Decisão

Este 550 específico é reconhecido, o oculto é removido e o envio é refeito.
Qualquer outro 550 continua subindo como erro.

### O caminho é derivado, não copiado da mensagem

A primeira versão usava o caminho que o servidor informa — e **ele vem
absoluto**: `/candidato/x/.in.index.html`. O resto da sessão trabalha em caminho
**relativo** à raiz da conta FTP, e o servidor resolve os dois de forma
diferente. O resultado, medido em 04/09/2026:

```
STOR candidato/x/index.html   → 550 Temporary hidden file … already exists
DELE /candidato/x/.in.index.html → 550 No such file or directory
```

O mesmo arquivo, existindo por um caminho e não existindo pelo outro. A
publicação morreu com **11.800 de 20.906** já enviados.

Hoje a mensagem serve só para **reconhecer** o caso; o endereço a apagar sai do
próprio destino, do mesmo jeito que o `STOR` monta o dele. Como efeito colateral,
um servidor hostil não tem como nos mandar apagar outra coisa — não importa o que
ele responda, o único caminho que este módulo apaga é o oculto do arquivo que ele
mesmo está tentando escrever.

### Não conseguir limpar não pode custar o resto do site

A primeira versão derrubava a publicação inteira quando a remoção falhava. Um
arquivo de 20.906 apagando o trabalho dos outros 20.905 é a troca errada.

O arquivo que não sobe fica **fora do manifesto** — e por ficar de fora, a
próxima publicação tenta de novo. Perder uma página até amanhã é
incomparavelmente melhor que perder a publicação inteira hoje. O log nomeia os
arquivos que ficaram para trás.

## Por que apagar aqui é seguro

O arquivo removido é um **upload parcial do próprio arquivo que estamos
reescrevendo**, no caminho que estamos prestes a ocupar. É a mesma categoria de
`_liberar_caminho`, que remove um diretório vazio ocupando o lugar de um arquivo:
remove-se o que **impede um arquivo de existir**, nunca o que é conteúdo.

## Consequências

- Publicação interrompida deixa de envenenar a próxima. Antes, a única saída era
  apagar o oculto à mão por FTP — acesso que só o dono da conta tem.
- Se a remoção falhar, o erro original sobe. Não engolimos o problema.
