# ADR-016 — Intermediário TLS versionado no repositório

**Status:** Aceita · **Data:** 2026-08-28 · **Feature:** F-04 (S8, IDEB)

## Contexto

O IDEB era a última lacuna de indicador do projeto, e a mais valiosa: bienal desde
2005, por UF, num tema de competência estadual direta. É a única série em que a
janela de um mandato de governador contém **duas ou três medições**.

A lacuna [L-05](../LACUNAS.md) atribuía a falha a "reset de conexão / bloqueio de
rede". A medição de 28/08/2026 mostrou outra coisa:

```
folha         CN=*.inep.gov.br                      válido (abr–out/2026)
intermediário CN=RNP ICPEdu GR46 OV TLS CA 2025     NÃO é enviado pelo servidor
raiz          CN=GlobalSign Root R46                já está na loja do sistema
```

Não falta autoridade confiável — **falta um elo**. O navegador disfarça o problema
porque busca o intermediário sozinho pela extensão AIA do certificado. O Python
não faz isso, e a conexão morre em `CERTIFICATE_VERIFY_FAILED` antes de qualquer
HTTP. Por isso o Windows "funcionava" e o Python não.

## Decisão

O intermediário fica **versionado** em `certs/rnp-icpedu-gr46-ov-tls-ca-2025.pem`,
e `ingest/common/http.py` o injeta **apenas para `download.inep.gov.br`**, via um
mapa `CADEIAS_INCOMPLETAS`.

### Por que não as alternativas

| Alternativa | Por que não |
|---|---|
| `verify=False` | Desliga a verificação inteira e abre a porta para interceptação. Trocaria um problema real por um risco maior. |
| `truststore` (loja do SO) | Resolve na máquina do Windows e **não** no Ubuntu do CI. O pipeline diário continuaria quebrado. |
| Trocar o bundle global | Afetaria TSE, IBGE, IPEA, Tesouro e Câmara para resolver um host. |
| Esperar o INEP corrigir | Fora do nosso controle, e a série é a mais valiosa que faltava. |

A verificação continua **completa**: a cadeia é validada até a GlobalSign Root R46
como em qualquer outro host. O repositório só devolve a peça que o servidor omitiu.
O arquivo é um certificado público, não um segredo — impressão SHA-256
`E1:07:47:D4:DA:7B:AB:09:CB:A9:95:2F:01:9D:35:34:CB:9F:BA:07:0B:F1:3D:87:91:B1:69:9C:D2:FF:59:DD`,
válido até 19/11/2030.

O mapa é por host, e não global, de propósito: se amanhã outro servidor público
tiver o mesmo defeito, entra uma linha; nenhum host herda a exceção sem que
alguém escreva o nome dele.

## Duas consequências que valem registro

**As URLs também precisaram ser descobertas.** A página de resultados do INEP não
tem link nenhum no HTML — seis padrões de URL tentados à mão deram 404. Os links
reais vêm de um endpoint declarado em `data-url` no próprio HTML
(`.../ideb/resultados/2005-2025`). O comando `verify` refaz essa descoberta e
**falha** se um dos arquivos em uso sumir da página; a carga usa nomes fixos,
porque baixar um arquivo diferente a cada execução em silêncio seria pior do que
parar.

**A planilha do INEP tem um defeito.** No arquivo do Brasil, a coluna do IDEB 2023
ficou sem o código de máquina `VL_OBSERVADO_2023`, embora o dado esteja lá (rede
pública = 4,7). Lendo só pelo código, o Brasil perderia 2023 e **27 estados
ficariam sem comparador naquele ano** — violação silenciosa da Constituição §0.2.
O parser recorre ao cabeçalho humano apenas nas colunas sem código, com um padrão
estreito (`IDEB 2023 (N x P)`): na mesma linha existe "Metas do 1º ciclo do Ideb",
e um padrão frouxo traria **meta** como se fosse resultado observado — exatamente
o que a Constituição §0.1 proíbe.

## Consequência

`IDEB` ingerido: **308 observações**, 28 unidades, 11 edições de 2005 a 2025, rede
pública, anos finais do ensino fundamental. Leitura de `xlsx` feita com stdlib
(`zipfile` + `ElementTree`), sem quebrar a regra do `pyproject` de que o núcleo da
ingestão não tem dependência externa.
