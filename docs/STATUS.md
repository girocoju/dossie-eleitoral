# Estado das Tasks

> Atualizado em **2026-08-27**. Fonte da verdade sobre o que esta' feito.
> Convencao: ✅ feito e verificado · 🟡 codigo pronto, execucao pendente · ⬜ nao iniciado
>
> O BigQuery esta' configurado: projeto `radar-brasil-ddi`, modo sandbox, datasets
> em `US`. As credenciais locais sao ADC (`gcloud auth application-default login`) —
> nao ha' chave de service account em disco. A configuracao local fica em `.env`
> (gitignored), incluindo o `RADAR_CPF_SALT`.

## Fase 0 — Setup

| Task | Estado | Nota |
|---|---|---|
| T-001 Repo, estrutura, `CLAUDE.md`, `.gitignore`, `pyproject.toml` | ✅ | Repo Git proprio inicializado na pasta do projeto |
| T-002 Projeto GCP, datasets, credenciais | ✅ | Projeto `radar-brasil-ddi` com faturamento ativo, orcamento de R$ 20 com alertas. Credencial local via ADC, sem chave de service account. Secrets do Actions ainda pendentes |
| T-003 dbt inicializado, `profiles.yml` por env var | ✅ | `dbt parse` limpo, 13 modelos, 107 testes, 0 deprecacoes |
| T-004 `dim_uf` e `dim_cargo` como seeds | ✅ | Gerados de `ingest/common/ufs.py` e do catalogo; teste impede divergencia |

**Aceite da fase:** `dbt debug` verde — ✅ `All checks passed` em 27/08/2026.

## Fase 1 — TSE 2026 ponta a ponta

| Task | Estado | Nota |
|---|---|---|
| T-101 `ingest/tse.py`: download, Latin-1, carga particionada | ✅ | Rodou contra o pacote real de 27/08/2026 |
| T-102 Bens, complementar, vagas, coligacoes | ✅ | 5 datasets, 28 arquivos cada |
| T-103 `stg_tse__candidaturas` + testes | ✅ | Materializado no BigQuery: 20.765 linhas, testes verdes |
| T-104 `dim_candidato`, `dim_partido`, `fct_candidatura` | ✅ | 20.765 / 30 / 20.765 linhas materializadas |
| T-105 Power BI: conexao + Visao Geral, Presidencia, Governadores | 🟡 | Modelo semantico TMDL escrito; visuais faltam ser montados no Desktop |

**Numeros reais da carga de 2026** (`data/staging/qa/`):

| Dataset | Linhas | Arquivos | UEs |
|---|---:|---:|---:|
| candidatos | 20.765 | 28 | 28 (27 UFs + BR) |
| complementar | 20.765 | 28 | — |
| bens | 76.410 | 28 | 28 |
| coligacoes | 4.331 | 28 | 28 |
| vagas | 191 | 28 | 28 |

Candidaturas por cargo: 1 Presidente 13 · 2 Vice-Presidente 13 · 3 Governador 198 ·
4 Vice-Governador 203 · 5 Senador 318 · 6 Dep. Federal 7.725 · 7 Dep. Estadual 11.207 ·
8 Dep. Distrital 429 · 9 1o Suplente 328 · 10 2o Suplente 331. Vagas em disputa: 1.790.

> **Correcao de 27/08/2026.** A primeira carga registrou o dobro disso (41.530
> candidaturas). O pacote do TSE traz, alem de um CSV por unidade eleitoral, um
> `_BRASIL` consolidado, e o `arquivo_regex` casava os dois. Corrigido, com duas
> travas novas no loader: a carga falha se o numero de unidades lidas nao for 28
> ou se alguma chave declarada se repetir. A segunda trava ja' pegou um erro
> independente — a chave declarada de `coligacoes` estava incompleta (o grao real
> e' coligacao x partido x cargo).

**Aceite F-01** (≥ 18.000 candidaturas e 27 UFs): ✅ 20.765 candidaturas, 27 UFs + BR.
**Conferencia amostral contra o DivulgaCandContas** (10 casos): ⬜ pendente.

## Fase 2 — Historico e mandatos

| Task | Estado | Nota |
|---|---|---|
| T-201 ADR: Base dos Dados vs. CSV bruto | ✅ | [ADR-004](adr/ADR-004-fonte-do-historico.md): CSV do TSE; BdD so' para conferencia |
| T-202 Ingestao do historico + resultados por UF | 🟡 | Ingestao roda para qualquer ano; layouts 1998–2022 nao conferidos ([L-01](LACUNAS.md)); votos nao ingeridos ([L-02](LACUNAS.md)) |
| T-203 Mapa de colunas por ano em `layouts/tse_{ano}.yml` | ✅ | **8 anos conferidos** contra os arquivos reais (L-01 fechada) |
| T-204 `fct_mandato` + teste de cobertura | 🟡 | Materializado com **0 linhas** — correto: em 2026 ninguem foi eleito ainda e o historico 1998–2022 nao entrou ([L-01](LACUNAS.md)) |
| T-205 Vinculacao de pessoa + relatorio de taxa de match | 🟡 | `analyses/relatorio_vinculacao_pessoa.sql` escrito; medicao pendente ([L-10](LACUNAS.md)) |

## Fase 3 — Socioeconomico e "Durante o mandato"

| Task | Estado | Nota |
|---|---|---|
| T-301 `ingest/ibge_sidra.py`, `ingest/ipeadata.py` | ✅ | 4 series conferidas contra a API real; S8–S10 em [LACUNAS](LACUNAS.md) |
| T-302 `fct_indicador_uf_ano` + `dim_indicador` | ✅ | 3.360 linhas, 5 indicadores, **0 sem comparador nacional** |
| T-303 `fct_mandato_indicador` com comparadores | 🟡 | Modelo constroi sem erro, mas sai **vazio**: depende de `fct_mandato`, que depende do historico ([L-01](LACUNAS.md)) |
| T-304 Paginas "Durante o Mandato" e "Contexto Socioeconomico" | 🟡 | Tabelas e medidas no modelo; visuais faltam |

**Dados socioeconomicos ja' extraidos** (`data/staging/indicadores/`): 1.596 observacoes
do SIDRA (PIB 2002–2023, populacao 2001–2025, desocupacao 2012–2025) e 1.260 do
Ipeadata (homicidios 1980–2024). Todas com 27 UFs + Brasil.

## Fase 4 — Polimento e publicacao

| Task | Estado | Nota |
|---|---|---|
| T-401 Pagina Metodologia + `docs/METODOLOGIA.md` | ✅ | Documento escrito; pagina do relatorio a montar |
| T-402 Perfil de candidatos completo (F-08) | 🟡 | Medidas de perfil no modelo; filtros a montar no Desktop |
| T-403 GitHub Actions semanal (F-10) | ✅ | `.github/workflows/pipeline.yml` — lint, pytest, dbt e ingestao agendada |
| T-404 Publish to web, README com prints, post | ⬜ | Depende de T-002 e do relatorio montado |

## Fase 5 — Pos-eleicao

F-11 (financiamento) e F-12 (resultados 2026): ⬜ fase 2 do produto, apos 25/10/2026.

---

## Materializado no BigQuery em 27/08/2026

`dbt build`: **123 de 123** (3 seeds, 8 modelos de tabela, 5 views, 107 testes),
`Completed successfully`.

| Tabela | Linhas |
|---|---:|
| `raw_tse.candidatos` | 20.765 |
| `raw_tse.bens` | 76.410 |
| `stg.stg_tse__candidaturas` | 20.765 |
| `stg.stg_indicadores` | 2.856 |
| `marts.dim_candidato` | 20.765 |
| `marts.dim_partido` | 30 |
| `marts.fct_candidatura` | 20.765 |
| `marts.fct_indicador_uf_ano` | 3.360 |
| `marts.fct_mandato` | **0** |
| `marts.fct_mandato_indicador` | **0** |

Os dois zeros sao o estado correto, nao uma falha: `fct_mandato` nasce de quem foi
eleito, e o unico ano carregado e' 2026, cuja eleicao ainda nao ocorreu. O modulo
"Durante o mandato" so' ganha conteudo quando o historico 1998–2022 entrar.

`fct_indicador_uf_ano` tem **0 linhas sem comparador nacional** — a regra da
Constituicao secao 2 esta' satisfeita no dado, nao so' no visual.

## O caminho critico

1. `make ingest-historico` — os 8 layouts ja' estao conferidos. E' isto que faz
   `fct_mandato` e o modulo "Durante o mandato" deixarem de ser vazios.
2. Montar os visuais no Power BI Desktop sobre o modelo TMDL ja' escrito,
   apontando `ProjetoGCP = radar-brasil-ddi` e `DatasetMarts = marts`.
3. Secrets do GitHub Actions (`RADAR_GCP_SA_JSON`, `RADAR_CPF_SALT`) para o
   pipeline agendado — o alvo `ci` usa service account, nao ADC.
