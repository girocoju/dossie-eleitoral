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

**Não é confiança cega na mensagem do servidor.** O caminho vem dela, mas só vale
se o nome do arquivo for exatamente `.in.<basename do destino>.` e estiver na
mesma pasta. Um servidor que respondesse `Temporary hidden file /etc/passwd
already exists` não consegue nos fazer apagar outra coisa — há teste para os três
casos adversariais.

Qualquer outro 550 continua subindo como erro.

## Por que apagar aqui é seguro

O arquivo removido é um **upload parcial do próprio arquivo que estamos
reescrevendo**, no caminho que estamos prestes a ocupar. É a mesma categoria de
`_liberar_caminho`, que remove um diretório vazio ocupando o lugar de um arquivo:
remove-se o que **impede um arquivo de existir**, nunca o que é conteúdo.

## Consequências

- Publicação interrompida deixa de envenenar a próxima. Antes, a única saída era
  apagar o oculto à mão por FTP — acesso que só o dono da conta tem.
- Se a remoção falhar, o erro original sobe. Não engolimos o problema.
