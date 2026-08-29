# ADR-021 — O nome que o certificado do FTP precisa cobrir

**Status:** Aceita · **Data:** 2026-08-29 · **Feature:** F-07 (ADR-018) · **Relacionada:** [ADR-016](ADR-016-cadeia-tls-incompleta.md)

## Contexto

A publicação diária do dossiê envia 792 arquivos por FTP para a Hostinger. FTP
simples manda **usuário e senha em texto puro**, e isso atravessaria a internet
aberta a cada execução, saindo de um runner do GitHub. Por isso `scripts/publicar.py`
usa `FTP_TLS` com `AUTH TLS` e `PROT P` (canal de dados também cifrado).

Na primeira execução real, a publicação falhou:

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
Hostname mismatch, certificate is not valid for 'ftp.datadubaintel.com'
```

## O que a medição mostrou

Sondagem do servidor em 29/08/2026, sem enviar credencial — o handshake para
antes do login:

| | |
|---|---|
| `AUTH TLS` | **aceito** — TLSv1.3, `TLS_AES_256_GCM_SHA384` |
| Emissor | Sectigo Public Server Authentication CA DV R36 |
| Subject | `CN=*.hstgr.io` |
| SANs | `*.hstgr.io`, `hstgr.io` |
| Validade | até **01/09/2026** |

**O servidor não recusou TLS.** Ele oferece TLS moderno com um certificado
legítimo e publicamente confiável — só que emitido para a infraestrutura da
Hostinger, não para o apelido DNS do cliente. É o normal em hospedagem
compartilhada, e a verificação falhou com razão: o certificado de fato não cobre
`ftp.datadubaintel.com`.

A primeira versão do módulo diagnosticou isso como *"o servidor recusou TLS"*.
Estava errado e mandaria quem lesse procurar no lugar errado.

## Decisão

Separar duas coisas que sempre foram duas:

| | variável | valor |
|---|---|---|
| onde conectar | `RADAR_FTP_HOST` | `ftp.datadubaintel.com` |
| quem deve estar lá | `RADAR_FTP_TLS_NOME` | `ftp.hstgr.io` |

`FTP_TLS` verifica o certificado contra `self.host`, no canal de controle
(`auth`) e no de dados (`ntransfercmd`). O módulo troca esse valor **depois** de
a conexão TCP estar feita e antes do handshake.

**A verificação continua completa.** `verify_mode` segue `CERT_REQUIRED` e
`check_hostname` segue `True`: cadeia até uma CA pública, validade e hostname.
Muda apenas contra *qual* nome — e o nome passa a ser o verdadeiro. Não existe
`CERT_NONE` no caminho de publicação.

Quando `RADAR_FTP_TLS_NOME` não é definida, o comportamento é o padrão: verificar
contra o próprio host de conexão. Servidor com certificado no próprio nome não
precisa de nada.

## O que isto prova, e o que não prova

**Prova:** que do outro lado está a Hostinger. Quem sequestrasse o DNS de
`datadubaintel.com` precisaria de um certificado publicamente confiável para
algum `*.hstgr.io` — teria que comprometer a Hostinger ou uma CA.

**Não prova:** *qual* máquina da Hostinger atendeu. `*.hstgr.io` é um wildcard
sobre a frota inteira. É a afirmação verdadeira disponível, e está registrada
aqui em vez de ficar implícita.

O valor não é segredo e por isso fica no YAML do workflow, legível em revisão, e
não num secret — esconder o nome de um certificado público só dificultaria a
auditoria.

## Alternativas descartadas

**Fixar o certificado**, como a [ADR-016](ADR-016-cadeia-tls-incompleta.md) fez
com a intermediária do INEP. Era o instinto, e o precedente existia. Não serve
aqui: o certificado medido **expira em 01/09/2026**, três dias depois de ter sido
lido. Uma impressão digital fixada quebraria a publicação na primeira renovação,
num sábado, sem ninguém entender o motivo.

**`check_hostname = False`.** Manteria a cifra e jogaria fora a autenticação:
qualquer certificado passaria, inclusive um autoassinado de um atacante. Trocar
verificação forte contra o nome certo por verificação nenhuma seria perder o
ponto inteiro do TLS.

**FTP simples.** É o que a válvula `RADAR_FTP_INSEGURO=1` permite, e ela existe
para ser difícil de ligar por acidente. Não é usada.

**Descobrir o hostname real do servidor.** Seria a solução ideal — verificação
contra o nome exato da máquina. Não há DNS reverso para `223.27.112.89`, e o
nome não é publicado. Se aparecer no hPanel algum dia, basta trocar o valor de
`RADAR_FTP_TLS_NOME`: nada mais muda.

## Consequência

`python -m scripts.publicar --certificado` mostra a identidade TLS do servidor —
cifra, SHA-256, nomes cobertos — e sugere o valor de `RADAR_FTP_TLS_NOME`. É o
único ponto do módulo que não verifica, existe só para diagnosticar, e **não
envia credencial**: para no `auth()`, antes do login.

É o comando que a mensagem de erro indica quando a verificação falha, para que
a próxima pessoa a topar com isto não precise refazer a investigação.
