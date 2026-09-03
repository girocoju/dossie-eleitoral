# ADR-039 — A publicação só envia o que mudou

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** ADR-027, ADR-037, ADR-038, F-18

## Contexto

A publicação enviava os 1.013 arquivos do site a cada execução, todos os dias.
Com 738 arquivos isso levava treze minutos e funcionava. A F-18 leva o site a
mais de 20 mil arquivos, e o mesmo comportamento levaria horas de sessão FTP
aberta contra um servidor que corta a conexão a cada ~100 arquivos (ADR-027).

O manifesto `.arquivos.json` já existia desde o ADR-037, guardando a **lista** do
que a publicação anterior deixou no servidor. Guardando também o **hash** de cada
arquivo, o mesmo download responde a outra pergunta: o que mudou.

Isso só passou a valer alguma coisa depois do ADR-038. Enquanto o rodapé trazia a
data global, 100% das páginas mudavam por dia e não havia nada a economizar.
Com a data por ficha, duas gerações consecutivas sem reingestão produzem 1.011
arquivos idênticos.

## Decisão

Manifesto v2: `{"versao": 2, "arquivos": {caminho: hash}}`, sha256 truncado em 16
hex. Arquivo cujo hash local bate com o do manifesto não sobe.

### O manifesto sobe por último — e isso é a decisão inteira

Ele subia primeiro, por ser o primeiro na ordem alfabética (`.arquivos.json`).
Mantendo isso, uma publicação interrompida na metade deixaria no servidor um
manifesto **afirmando o hash de arquivos que nunca chegaram**. A publicação
seguinte pularia exatamente esses, e a página errada ficaria congelada no ar —
sem erro em lugar nenhum, sem nada no log, para sempre.

Subindo por último, o manifesto só descreve publicação que terminou. O pior caso
vira o caso seguro: o manifesto antigo continua lá, e a próxima publicação
reenvia o que já tinha subido. Custa banda, nunca correção.

Pela mesma razão, falhar ao gravar o manifesto **não** derruba a publicação: o
site já subiu inteiro; perder o manifesto custa um envio completo na próxima vez.

### O que faz tudo subir de novo

- manifesto v1 (lista de nomes, sem hash) — o formato antigo;
- manifesto ausente, ilegível ou de formato desconhecido;
- `--completo`, para quando o servidor e o manifesto discordarem.

Nenhum desses é um erro: reenviar é sempre seguro.

## Consequências

- A publicação diária passa de 1.013 arquivos para a ordem de algumas centenas.
- O orçamento de reconexão deixa de ser 40 fixo e passa a acompanhar o tamanho do
  site (1 a cada 50 arquivos, piso de 40). Quarenta era folga para 738 e seria
  teto para 20 mil — o que precisa ter limite é a **taxa** de quedas.
- A limpeza de órfãs (ADR-037) continua lendo o mesmo manifesto, agora pelas
  chaves. Nada mudou ali.
