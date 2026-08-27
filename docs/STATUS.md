# Estado das Tasks

> Atualizado em **2026-08-27**. Fonte da verdade sobre o que esta' feito.
> Convencao: ✅ feito e verificado · 🟡 codigo pronto, execucao pendente · ⬜ nao iniciado
>
> "Execucao pendente" quase sempre significa **falta de projeto GCP com credenciais**
> (T-002). Todo o resto do pipeline foi exercitado contra os arquivos reais das
> fontes, com `--target local`.

## Fase 0 — Setup

| Task | Estado | Nota |
|---|---|---|
| T-001 Repo, estrutura, `CLAUDE.md`, `.gitignore`, `pyproject.toml` | ✅ | Repo Git proprio inicializado na pasta do projeto |
| T-002 Projeto GCP, datasets, service account, secrets | ⬜ | **Depende de voce.** Ver [README](../README.md#3-configurar-o-bigquery) |
| T-003 dbt inicializado, `profiles.yml` por env var | ✅ | `dbt parse` limpo, 13 modelos, 107 testes, 0 deprecacoes |
| T-004 `dim_uf` e `dim_cargo` como seeds | ✅ | Gerados de `ingest/common/ufs.py` e do catalogo; teste impede divergencia |

**Aceite da fase:** `dbt debug` verde — 🟡 pendente de T-002 (`dbt parse` ja' passa).

## Fase 1 — TSE 2026 ponta a ponta

| Task | Estado | Nota |
|---|---|---|
| T-101 `ingest/tse.py`: download, Latin-1, carga particionada | ✅ | Rodou contra o pacote real de 27/08/2026 |
| T-102 Bens, complementar, vagas, coligacoes | ✅ | 5 datasets, 29 arquivos cada |
| T-103 `stg_tse__candidaturas` + testes | 🟡 | Modelo e testes escritos; falta `dbt run` com credenciais |
| T-104 `dim_candidato`, `dim_partido`, `fct_candidatura` | 🟡 | idem |
| T-105 Power BI: conexao + Visao Geral, Presidencia, Governadores | 🟡 | Modelo semantico TMDL escrito; visuais faltam ser montados no Desktop |

**Numeros reais da carga de 2026** (`data/staging/qa/`):

| Dataset | Linhas | Arquivos | UEs |
|---|---:|---:|---:|
| candidatos | 41.530 | 29 | 28 (27 UFs + BR) |
| complementar | 41.530 | 29 | — |
| bens | 152.820 | 29 | 28 |
| coligacoes | 8.662 | 29 | 28 |
| vagas | 382 | 29 | 28 |

Candidaturas por cargo: 1 Presidente 26 · 2 Vice-Presidente 26 · 3 Governador 396 ·
4 Vice-Governador 406 · 5 Senador 636 · 6 Dep. Federal 15.450 · 7 Dep. Estadual 22.414 ·
8 Dep. Distrital 858 · 9 1o Suplente 656 · 10 2o Suplente 662.

**Aceite F-01** (≥ 18.000 candidaturas e 27 UFs): ✅ 41.530 candidaturas, 27 UFs + BR.
**Conferencia amostral contra o DivulgaCandContas** (10 casos): ⬜ pendente.

## Fase 2 — Historico e mandatos

| Task | Estado | Nota |
|---|---|---|
| T-201 ADR: Base dos Dados vs. CSV bruto | ✅ | [ADR-004](adr/ADR-004-fonte-do-historico.md): CSV do TSE; BdD so' para conferencia |
| T-202 Ingestao do historico + resultados por UF | 🟡 | Ingestao roda para qualquer ano; layouts 1998–2022 nao conferidos ([L-01](LACUNAS.md)); votos nao ingeridos ([L-02](LACUNAS.md)) |
| T-203 Mapa de colunas por ano em `layouts/tse_{ano}.yml` | ✅ | 8 anos declarados; 2026 conferido contra o arquivo real |
| T-204 `fct_mandato` + teste de cobertura | 🟡 | Modelo e teste `assert_cobertura_governadores_e_presidentes` escritos |
| T-205 Vinculacao de pessoa + relatorio de taxa de match | 🟡 | `analyses/relatorio_vinculacao_pessoa.sql` escrito; medicao pendente ([L-10](LACUNAS.md)) |

## Fase 3 — Socioeconomico e "Durante o mandato"

| Task | Estado | Nota |
|---|---|---|
| T-301 `ingest/ibge_sidra.py`, `ingest/ipeadata.py` | ✅ | 4 series conferidas contra a API real; S8–S10 em [LACUNAS](LACUNAS.md) |
| T-302 `fct_indicador_uf_ano` + `dim_indicador` | 🟡 | Modelo escrito; seed gerado do catalogo |
| T-303 `fct_mandato_indicador` com comparadores | 🟡 | Modelo escrito, com `delta_vs_brasil`, `delta_vs_regiao`, `janela_incompleta` |
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

## O caminho critico

1. **T-002** — criar o projeto GCP e a service account. Tudo em 🟡 destrava aqui.
2. `make dbt-build` — primeira materializacao; os 107 testes viram verificacao de verdade.
3. **L-01** — `make verify-layout ANO=...` para os sete anos historicos.
4. Montar os visuais no Power BI Desktop sobre o modelo TMDL ja' escrito.
