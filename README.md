# Radar Brasil — Raio-X Eleitoral 2026

Hub analitico sobre as eleicoes gerais de 2026: **quem** sao os candidatos a
Presidente, Governador, Senador e Deputado, e **em que contexto socioeconomico**
eles concorrem — incluindo o que aconteceu com os indicadores da UF durante
mandatos anteriores de quem ja' governou.

Pipeline completo sobre dados publicos: **TSE / IBGE / IPEA / INEP / Tesouro → BigQuery → dbt → site estatico**.

O produto publico chama-se **Dossie Eleitoral**: uma ficha por candidato, com URL
propria, gerada uma vez por dia a partir do lake ([ADR-018](docs/adr/ADR-018-site-estatico-em-vez-de-bi.md)).

> **Correlacao nao e' causalidade — e o produto diz isso na tela.**
> O modulo "Durante o mandato" mostra o que aconteceu no periodo, sempre ao lado
> do Brasil e da regiao. Ele nao mede o efeito de nenhum governo, e o projeto nao
> ranqueia politicos. Ver [SPEC secao 0](SPEC.md) e [METODOLOGIA](docs/METODOLOGIA.md).

Peca de portfolio da **Data Duba Intelligence**.

---

## Estado atual

O pipeline de ingestao foi exercitado contra os **arquivos reais** das fontes em
**27/08/2026**:

| Fonte | O que veio | Periodo |
|---|---:|---|
| TSE — candidaturas 2026 | 20.765 linhas, 27 UFs + BR | 2026 |
| TSE — bens declarados | 76.410 linhas | 2026 |
| TSE — complementar, vagas, coligacoes | 25.287 linhas | 2026 |
| IBGE/SIDRA — PIB, populacao, desocupacao | 1.596 observacoes | 2001–2025 |
| IPEA — taxa de homicidios | 1.260 observacoes | 1980–2024 |

O modelo dbt (22 modelos, 207 testes) e a documentacao de metodologia estao
escritos; falta a **materializacao no BigQuery**, que depende de um projeto GCP.
O que esta' feito, o que falta e por que: [docs/STATUS.md](docs/STATUS.md).

## Arquitetura

```
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   ┌───────────────┐
│ Fontes       │──▶│ ingest/ (py) │──▶│ BigQuery         │──▶│ Site estatico │
│ TSE IBGE IPEA│   │ download +   │   │ raw → stg → marts│   │ Import mode   │
│              │   │ load raw     │   │ (dbt)            │   │ HTML + JSON   │
└──────────────┘   └──────────────┘   └──────────────────┘   └───────────────┘
                          │                    ▲
                          └── GitHub Actions ──┘
```

- `raw_*` — copia fiel da fonte, tudo STRING, particionada por ano.
- `stg` — tipagem, limpeza de sentinelas do TSE, schema unico entre anos.
- `marts` — modelo estrela consumido pelo gerador do site.

## Como rodar

### 1. Bootstrap

```bash
make bootstrap
```

Cria o venv, instala dependencias e os pacotes dbt. Usa `uv` se estiver instalado.

### 2. Ingestao sem BigQuery (funciona ja')

```bash
make verify-layout ANO=2026                              # confere o header real do TSE
python -m ingest.tse load --ano 2026 --target local      # baixa e converte para NDJSON
python -m ingest.ibge_sidra load --target local
python -m ingest.ipeadata  load --target local
```

Os arquivos ficam em `data/staging/` e o relatorio de carga em `data/staging/qa/`.
Nada disso precisa de credencial.

### 3. Configurar o BigQuery

O projeto roda em **BigQuery sandbox**: sem cartao de credito, custo zero
garantido ([ADR-009](docs/adr/ADR-009-particionamento-sandbox.md)).

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project SEU_PROJETO
```

Depois crie um `.env` na raiz (ele esta' no `.gitignore`):

```bash
RADAR_GCP_PROJECT=seu-projeto
RADAR_BQ_LOCATION=US                  # ver ADR-003
RADAR_DBT_TARGET=dev
RADAR_CPF_SALT=um-segredo-longo       # ver ADR-006 — sem isto o hash nao protege o CPF
```

E carregue antes de rodar: `set -a; . ./.env; set +a`.

O alvo `dev` do dbt usa OAuth/ADC — **nao ha' arquivo de chave de service
account em lugar nenhum**. Os datasets sao criados sozinhos na primeira carga.
Para o GitHub Actions, o alvo `ci` usa uma service account passada por secret.

### 4. Pipeline completo

```bash
make run          # ingest 2026 + historico + socioeconomico + dbt build
make test         # pytest + dbt test
```

## Estrutura

```
ingest/            ingestao (stdlib; BigQuery so' na hora de carregar)
  layouts/         layout do TSE por ano + catalogo de indicadores  ← o coracao do projeto
  common/          download com cache/sha256, resolucao de layout, normalizacao
dbt/               staging + marts, 107 testes
bi/                ARQUIVADO — modelo Power BI, ver ADR-018
docs/              METODOLOGIA, LACUNAS, STATUS, ADRs
scripts/           geradores de seed e do site
tests/             pytest (87 testes, sem rede)
```

## Duas decisoes que explicam o resto do codigo

**1. O layout do TSE nao e' adivinhado.** Cada ano tem um YAML declarando quais
nomes de coluna sao aceitos para cada campo. Na leitura, o header real e'
conferido: campo obrigatorio ausente **falha a carga** apontando o `leiame.pdf`;
coluna nao mapeada vai para `_extras` em vez de ser descartada.

Isso nao e' zelo abstrato. A conferencia do pacote de 2026 mostrou que o TSE
**partiu o cadastro em dois arquivos**: `ST_REELEICAO`, `VR_DESPESA_MAX_CAMPANHA`
e a situacao de julgamento migraram para o `consulta_cand_complementar`. Um
leitor que assumisse o layout de 2022 leria 2026 com metade dos campos nulos, em
silencio.

O mesmo pacote guarda uma segunda armadilha: alem de um CSV por unidade
eleitoral, ele traz um `_BRASIL` **consolidado**. Ler os dois dobra cada
candidatura sem nenhum sinal de erro — todos os totais continuam plausiveis. Por
isso a ingestao tambem falha quando o numero de unidades lidas nao e' 28 ou
quando uma chave declarada se repete. Ver
[ADR-008](docs/adr/ADR-008-layout-declarativo.md).

**2. O CPF nunca chega ao warehouse.** Ele e' transformado em HMAC-SHA256 durante
a leitura do CSV e o valor original nao e' gravado em lugar nenhum — nem no
arquivo local, nem no BigQuery. E' HMAC com salt, e nao SHA-256 puro, porque o
espaco de CPFs e' pequeno o bastante para ser enumerado por forca bruta: um hash
sem chave devolveria o CPF que o projeto se comprometeu a nao expor. E-mail e
titulo de eleitor sao descartados na leitura.
Ver [ADR-006](docs/adr/ADR-006-hmac-no-cpf.md) e [ADR-007](docs/adr/ADR-007-hash-na-ingestao.md).

## Documentacao

| Documento | Para que |
|---|---|
| [SPEC.md](SPEC.md) | A especificacao. Nada e' implementado fora dela |
| [CLAUDE.md](CLAUDE.md) | Regras de trabalho no repo |
| [docs/METODOLOGIA.md](docs/METODOLOGIA.md) | O que o projeto afirma e o que nao afirma |
| [docs/LACUNAS.md](docs/LACUNAS.md) | Dado ausente, registrado — nunca preenchido |
| [docs/STATUS.md](docs/STATUS.md) | Estado de cada Task |
| [docs/adr/](docs/adr/) | Decisoes de arquitetura |
| [bi/README.md](bi/README.md) | Diretorio arquivado — por que o Power BI saiu |

## Licenca

Codigo sob MIT. Os dados sao publicos e pertencem as suas fontes originais
(TSE, IBGE, IPEA), citadas em toda visualizacao.
