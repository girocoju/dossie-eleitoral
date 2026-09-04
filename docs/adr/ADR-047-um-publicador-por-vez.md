# ADR-047 — Um publicador por vez

**Status:** Aceita · **Data:** 2026-09-04 · **Relacionada:** ADR-027, ADR-039, ADR-045, ADR-036

## Contexto

Entre 03 e 04/09/2026 a publicação falhou quatro vezes, cada uma com um sintoma
diferente: conexão cortada, reconexão que não respondia, arquivo oculto que não
saía. Cada sintoma recebeu uma correção, e todas eram necessárias.

Nenhuma delas era a causa.

**A causa era haver dois publicadores.** O workflow do GitHub disparava o
pipeline inteiro — publicação incluída — a **cada push em `main`**, e o
`atualizar.bat` publica da máquina. Numa noite de nove commits:

```
#86  13:42→cancelado   concorreu 2h22 com uma publicacao local
#85  04:49→12:54       cancelado no meio do envio
#84  03:50→04:50       cancelado no meio do envio
#83  02:54→03:51       cancelado no meio do envio
#82  02:41→02:55       cancelado no meio do envio
#81  02:08→02:42       cancelado no meio do envio
#80  01:02→02:09       cancelado no meio do envio
#79  23:14→06:41       cancelado no meio do envio
#78  22:42→23:16       cancelado no meio do envio
```

Nove publicações de 20 mil arquivos, cada uma cancelada pela seguinte **no meio
do envio** — porque o job `pipeline` tem `cancel-in-progress: true`, e o job
`publicar` morre junto com ele.

Cancelar um `STOR` em voo é exatamente o que deixa o arquivo oculto
`.in.<nome>.` no servidor. As quedas que o ADR-045 tratou como instabilidade de
rede eram, em boa parte, dois clientes FTP disputando os mesmos caminhos.

O aviso já estava escrito no cabeçalho do próprio workflow, desde 31/08:

> *"Ter os dois agendados duplicaria a carga e faria dois FTP simultâneos no
> mesmo destino."*

Ele considerava o **agendamento**. Push faz exatamente a mesma coisa, e ninguém
tinha ligado uma coisa à outra — eu inclusive, que passei a noite corrigindo
sintomas com esse parágrafo a três linhas de distância.

## Decisão

### 1. Push não carrega nem publica

Push em `main` roda `verificar` (lint, testes, `dbt parse`) e para ali. Carga e
publicação só por **disparo manual** — `Actions → pipeline → Run workflow` — que
continua sendo a rede de segurança de um clique, inclusive com
`somente_publicar`.

Um commit de código não muda dado. Republicar 20 mil arquivos a cada commit era
trabalho puro, e trabalho que se atropelava.

### 2. A publicação trava o servidor enquanto roda

`.publicando.json`, escrito antes do primeiro `STOR` e removido no fim. Quem
chega e encontra trava viva **para**, dizendo de quem é e há quanto tempo:

```
JA' HA' UMA PUBLICACAO EM ANDAMENTO, iniciada ha' 1.5h por GitHub Actions,
run 33879527736.
  Espere ela terminar. Se tiver certeza de que morreu, use --forcar.
```

A trava **não é atômica** — FTP não oferece isso — e não precisa ser. O caso real
não é corrida de milissegundos: é uma publicação de duas horas começando enquanto
outra de duas horas está na metade.

**Trava com mais de 5 horas é considerada órfã e assumida.** Publicação morta não
pode bloquear o site até alguém entrar por FTP. Cinco horas é mais que a mais
longa já medida (2h22 local, 4h33 no runner antes de ser morta pelo teto de 6h) e
menos que o intervalo entre duas atualizações diárias.

**Não conseguir gravar a trava não impede publicar.** Ela é proteção contra
coincidência, não permissão de acesso — seguir sem ela é o que este projeto fez a
vida toda.

## O custo que estava escondido no meio disso

Com o problema à vista, um terceiro apareceu: `_liberar_caminho` fazia um `RMD`
antes de **todo** `STOR`, e ele quase sempre falha porque o caminho não é
diretório. Com 20.906 arquivos são 20.906 idas ao servidor só para ouvir "não é
diretório" — o dobro do tráfego de comandos.

Isso importa porque o runner do GitHub tem **teto de 6 horas**, e a publicação
estava em 14.000 de 20.907 depois de 4h33: ela seria morta antes do fim, sem
gravar manifesto e deixando mais resíduo.

O reparo continua completo; passou a ser **reação ao 550** `Not a regular file`,
e não rotina. Quem paga o custo é o caso raro, não os outros 20.905.

## Consequências

- Publicações concorrentes deixam de acontecer por construção, não por disciplina.
- Push volta a ser barato: minutos de verificação em vez de horas de pipeline.
- A atualização diária continua sendo o `atualizar.bat`, como decidido em 31/08.
- Se o `atualizar.bat` e um disparo manual coincidirem, o segundo para com uma
  mensagem que diz o que fazer.
