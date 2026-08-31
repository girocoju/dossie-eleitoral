# ADR-027 — Queda de conexão não derruba a publicação inteira

**Status:** Aceita · **Data:** 2026-08-31 · **Relacionada:** ADR-022 (fonte indisponível não derruba a carga), ADR-021, ADR-026

## Contexto

A publicação do site são **793 arquivos, 41 MB**, numa sessão FTP única que fica
aberta por volta de quatro minutos. Não havia retentativa: qualquer falha
derrubava tudo.

Em 31/08/2026, publicando o site logo após o rename (ADR-026), o servidor da
Hostinger cortou a conexão no meio e a publicação morreu com
`ConnectionResetError` — depois de centenas de arquivos já terem subido. O site
ficou com **metade das páginas novas e metade antigas**, cada metade apontando
para um endereço diferente. Pior que não ter publicado.

E não foi acaso: na execução seguinte, já com a correção, o servidor cortou a
conexão **quatro vezes** — a cada 100 a 200 arquivos, de forma consistente. Sem
retomada, publicar o site simplesmente não era possível, e não apenas frágil.

## Decisão

Cada arquivo tem até **4 tentativas**, com espera de 2s, 4s e 8s. Ao cair, o
script **reconecta e continua do mesmo arquivo** — não recomeça do zero e não
reenvia o que já subiu. Acima de **40 reconexões** numa mesma publicação, aborta
dizendo que aquilo deixou de ser instabilidade de rede.

### O que é instabilidade e o que é erro de verdade

A distinção é a mesma do ADR-022, transposta de HTTP para FTP:

| Situação | Classe | Tratamento |
|---|---|---|
| Conexão cortada, timeout, EOF | `OSError`, `EOFError` | reconecta e continua |
| Resposta 4xx do servidor | `ftplib.error_temp` | reconecta e continua |
| Resposta 5xx — caminho errado, permissão negada | `ftplib.error_perm` | **sobe, falha alto** |

`error_perm` fica **de propósito fora** da lista de transitórias. Um 550 é o
servidor dizendo que aquele caminho não pode receber aquele arquivo; reconectar
não muda isso, só transformaria um erro claro em quatro tentativas e um erro
tardio. Foi um 550 mal interpretado que criou um diretório `index.html` e
quebrou a home em 29/08.

### Por que reconectar em vez de só repetir

Depois de um reset, a sessão está morta: repetir o `STOR` nela só produz o mesmo
erro. E as pastas já criadas continuam existindo do outro lado, então o conjunto
`feitas` segue válido depois de reconectar — não há trabalho refeito.

## Consequências

- Publicação parcial deixa de ser um estado possível por queda de rede. Continua
  possível por interrupção manual, e aí a correção é rodar de novo.
- O log passa a mostrar as reconexões. Isso é informação, não ruído: se um dia
  forem 40, o script para e diz que o problema é outro.
- `enviar()` aceita `reconectar=None` e, sem ele, se comporta exatamente como
  antes — o `--dry-run` e quem chama direto não mudam.
