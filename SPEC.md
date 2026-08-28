# Radar Brasil — Raio-X Eleitoral 2026
## Spec-Driven Development (SDD) para uso com Claude Code

> **Como usar este arquivo no Claude Code**
> 1. Coloque-o na raiz do repo como `SPEC.md` (ou em `specs/001-raio-x-eleitoral.md`).
> 2. Crie um `CLAUDE.md` curto apontando para ele: *"Leia SPEC.md antes de qualquer tarefa. Nunca implemente algo que não esteja em uma Feature (F-xx) ou Task (T-xx). Se precisar de algo fora do spec, proponha uma alteração no spec primeiro."*
> 3. Trabalhe por fase: peça ao Claude Code para executar as Tasks de uma fase, rodar os critérios de aceite, e só então avançar.
> 4. Toda decisão nova vira uma linha na seção **ADRs**. Toda dúvida vira uma linha em **Perguntas em aberto**.

---

## 0. Constituição (princípios inegociáveis)

1. **Apartidário e descritivo.** O projeto mostra dados; não emite juízo sobre candidatos ou partidos. Textos, cores e rótulos não podem favorecer nenhum lado. Nenhum ranking de "melhor/pior político".
2. **Correlação não é causalidade — e o produto diz isso na tela.** Todo indicador socioeconômico cruzado com mandato é apresentado como *"o que aconteceu na região/país durante o mandato"*, sempre ao lado de um comparador (média nacional, UF vizinha, período anterior). Nunca como "resultado do candidato".
3. **Somente dados públicos, com fonte e data de extração em toda visualização.**
4. **Reprodutível do zero.** `make bootstrap && make run` (ou equivalente) recria tudo a partir das fontes originais. Nada de CSV editado na mão.
5. **Custo próximo de zero.** BigQuery dentro do free tier (10 GB storage / 1 TB query por mês). Power BI em modo *Import* sobre tabelas agregadas — nunca DirectQuery em tabela grande.
6. **Versionado.** Código, SQL, modelos dbt e o arquivo `.pbip`/`.pbit` no GitHub. Sem dados brutos no repo (`.gitignore` em `data/`).
7. **LGPD/ética.** Dados de candidatos são públicos por lei, mas o projeto não expõe CPF nem endereço, e não cruza com dados de terceiros que não sejam agregados.

---

## 1. Visão e problema

**Uma frase:** um hub analítico que mostra *quem* são os candidatos das eleições gerais de 2026 (Presidente, Governador, Senador, Deputado Federal, Deputado Estadual/Distrital) e *em que contexto socioeconômico* concorrem — incluindo o que aconteceu nos indicadores de sua UF/país durante mandatos anteriores de quem tenta reeleição ou já governou.

**Por que existe:** peça de portfólio da Data Duba Intelligence (DDI) demonstrando pipeline completo (ingestão → BigQuery → dbt → Power BI) sobre dados públicos brasileiros, com gancho de atualidade (eleições 2026, 1º turno em 04/10/2026).

**Público:** recrutadores e potenciais clientes da DDI (primário); jornalistas de dados e eleitores curiosos (secundário).

---

## 2. Escopo

### 2.1 Dentro do escopo (MVP — entrega antes do 1º turno)
- Candidatos 2026 de todos os cargos em disputa, todas as UFs.
- Perfil: cargo, UF, partido, coligação/federação, gênero, cor/raça, idade, grau de instrução, ocupação, situação da candidatura, reeleição (sim/não), bens declarados.
- **Foto oficial de urna de cada candidato de 2026** (F-13 — *proposta, aguardando aprovação*).
- Histórico: eleições gerais 1998–2022 (candidaturas e resultados) para montar *"quem já ocupou o cargo"*.
- Contexto socioeconômico por UF e Brasil: PIB e PIB per capita, população, desemprego (PNAD Contínua), IDHM, mortalidade infantil, IDEB, homicídios (Atlas da Violência/IPEA), receita/despesa pública (SICONFI).
- Módulo *"Durante o mandato"*: para candidatos que foram Governador ou Presidente em mandato anterior, série dos indicadores da UF/Brasil no período do mandato vs. comparadores.
- Hub no Power BI com páginas: Visão Geral → Presidência → Governadores → Senado → Câmara → Assembleias → Contexto Socioeconômico → Durante o Mandato → Metodologia/Fontes.

### 2.2 Fora do escopo (explicitamente)
- Propostas de governo (texto livre) — fase futura.
- Prestação de contas / financiamento de campanha — fase 2 (dados só ficam completos após a eleição).
- Resultados 2026 — fase 2 (após 04/10 e 25/10).
- Qualquer modelo preditivo de resultado eleitoral.
- Qualquer inferência causal ("o governador X gerou Y").
- Dados municipais no MVP (prefeito/vereador não estão em disputa em 2026). Granularidade mínima é UF.
- Deputados e senadores no módulo "Durante o mandato" — o vínculo indivíduo↔indicador regional é fraco demais; eles aparecem só com perfil e histórico eleitoral.

---

## 3. Fontes de dados

| ID | Fonte | O que traz | Formato / acesso | Observações |
|---|---|---|---|---|
| S1 | TSE Dados Abertos — `consulta_cand_{ano}.zip` | Candidatos, 1998–2026 | CSV, `;`, **Latin-1**, um arquivo por UF + BRASIL | Layout muda entre anos; usar o `leiame.pdf` de cada ano para mapear colunas |
| S2 | TSE — `bem_candidato_{ano}.zip` | Bens declarados | CSV, mesmo padrão | Valor em string com vírgula decimal |
| S3 | TSE — `consulta_cand_complementar_2026.zip` | Campos extras 2026 | CSV | Verificar conteúdo no leiame |
| S4 | TSE — `votacao_candidato_munzona_{ano}.zip` | Votos por candidato/município/zona | CSV, grande (GBs) | Só 1998–2022 no MVP; agregar para UF antes de subir ao Power BI |
| S5 | TSE — `consulta_vagas_{ano}.zip`, `consulta_coligacao_{ano}.zip` | Vagas e coligações | CSV | |
| S6 | IBGE SIDRA (API) | PIB (5938), população (6579), PNAD desemprego (4099/6381) | JSON via `https://apisidra.ibge.gov.br` | Códigos de tabela devem ser confirmados no ato |
| S7 | IPEA — Ipeadata (API) | Séries macro (inflação, câmbio, etc.) e Atlas da Violência | JSON via `http://www.ipeadata.gov.br/api/odata4/` | |
| S8 | Atlas do Desenvolvimento Humano (PNUD/IPEA/FJP) | IDHM por UF (2010, 2021) | CSV/XLSX | Série curta — usar com cautela |
| S9 | DATASUS / SIM-SINASC | Mortalidade infantil por UF | TabNet / CSV | Alternativa: série pronta no Ipeadata |
| S10 | INEP | IDEB por UF | XLSX | Bienal |
| S11 | Tesouro — SICONFI | Receita/despesa dos estados | API/CSV | Opcional no MVP |
| S12 | **Base dos Dados** (`basedosdados` no BigQuery) | Versões já tratadas de TSE, IBGE, IPEA | SQL direto no BigQuery | **Atalho recomendado para o histórico 1998–2022.** Verificar cobertura de 2026 antes de depender; para 2026 usar S1–S3 direto |
| S13 | TSE — `foto_cand{ano}_{UF}_div.zip` | Foto de cada candidato | ZIP de JPG, um por UF, em `eleicoes/eleicoes{ano}/fotos/` | **Confirmada disponível em 27/08/2026** (AC 2,3 MB · DF 3,9 MB · SP 15,4 MB · BR 0,3 MB). ~150–250 MB no total de 2026 — não vai para o BigQuery; destino natural é bucket público no Cloud Storage, com a URL na `dim_candidato`. Proposta de inclusão pendente de decisão |
| S14 | TSE — DivulgaCandContas | Proposta de governo (PDF) | Uma requisição por candidato | **Não existe em lote** — ver docs/LACUNAS.md, L-17. Só obrigatória para majoritários: 529 de 20.765 candidaturas em 2026 |

**Regra:** cada fonte tem um script/idempotente em `ingest/` que baixa, valida hash, e carrega em `raw_*`. A data de extração é gravada em coluna `_extracted_at`.

---

## 4. Arquitetura

```
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   ┌───────────────┐
│ Fontes       │──▶│ ingest/ (py) │──▶│ BigQuery         │──▶│ Power BI      │
│ TSE IBGE IPEA│   │ download +   │   │ raw → stg → marts│   │ Import mode   │
│ basedosdados │   │ load raw     │   │ (dbt)            │   │ .pbip no git  │
└──────────────┘   └──────────────┘   └──────────────────┘   └───────────────┘
                          │                    ▲
                          └── GitHub Actions ──┘ (agendado + manual)
```

- **Linguagem:** Python 3.11+, `uv` para dependências.
- **Warehouse:** BigQuery, projeto `radar-brasil`, datasets `raw_tse`, `raw_ibge`, `raw_ipea`, `stg`, `marts`. Localização `southamerica-east1` ou `US` (decidir — ver ADR-003).
- **Transformação:** dbt-core + dbt-bigquery. Testes de schema obrigatórios em toda tabela de `marts`.
- **Orquestração:** GitHub Actions (cron semanal até a eleição; manual depois). Sem Airflow no MVP.
- **BI:** Power BI Desktop; arquivo salvo como `.pbip` (formato de projeto, versionável). Publicação via Power BI Service → *Publish to web* para o portfólio público.
- **Camadas de dados:**
  - `raw_*`: cópia fiel da fonte, tipos STRING, particionado por `ano_eleicao` quando aplicável.
  - `stg_*`: tipagem, renomeação para snake_case em pt-BR, deduplicação, padronização de códigos (UF, cargo, partido).
  - `marts`: modelo estrela consumido pelo Power BI.

---

## 5. Modelo de dados (`marts`)

### Dimensões
- `dim_candidato` — `sq_candidato` (chave TSE por eleição), `nome_urna`, `nome_completo`, `cpf_hash` (SHA-256 para linkar entre anos sem expor CPF), `genero`, `cor_raca`, `data_nascimento`, `grau_instrucao`, `ocupacao`, `url_foto` e `tem_foto` (F-13 — *proposta*).
- `dim_partido` — `sigla`, `nome`, `numero`, `federacao` (2022+).
- `dim_cargo` — `cod_cargo`, `descricao`, `esfera` (federal/estadual), `vagas_2026`.
- `dim_uf` — `sg_uf`, `nome`, `regiao`, `cod_ibge`.
- `dim_tempo` — ano (para indicadores anuais) e `ano_eleicao`.
- `dim_indicador` — `cod_indicador`, `nome`, `fonte`, `unidade`, `periodicidade`, `direcao_desejavel` (↑ ou ↓, usado só para cor neutra de tendência — ver Constituição 1).

### Fatos
- `fct_candidatura` — grão: uma candidatura (candidato × cargo × UF × ano). Colunas: `sq_candidato`, `ano_eleicao`, `cod_cargo`, `sg_uf`, `sigla_partido`, `situacao_candidatura`, `is_reeleicao`, `total_bens_declarados`, `n_bens`, `situacao_turno` (eleito / não eleito / 2º turno), `votos_nominais` (quando houver resultado).
- `fct_mandato` — grão: um mandato exercido. Derivado de `fct_candidatura` onde `situacao_turno = eleito`. Colunas: `cpf_hash`, `cod_cargo`, `sg_uf` (ou `BR`), `ano_inicio`, `ano_fim`, `motivo_fim` (fim regular / renúncia / cassação — se disponível em S5 "motivo da cassação").
- `fct_indicador_uf_ano` — grão: indicador × UF × ano. Colunas: `cod_indicador`, `sg_uf`, `ano`, `valor`, `valor_brasil` (mesmo indicador, agregado nacional, para comparador), `_extracted_at`.
- `fct_mandato_indicador` — grão: mandato × indicador. Colunas: `valor_inicio`, `valor_fim`, `variacao_abs`, `variacao_pct`, `variacao_brasil_pct` (mesmo período, Brasil), `variacao_regiao_pct` (média da região), `delta_vs_brasil` = `variacao_pct − variacao_brasil_pct`. **Este é o "durante o mandato". Nunca chamar de "resultado".**

### Regras de negócio críticas
- **Vínculo entre anos:** `cpf_hash` é a chave de pessoa. Onde o CPF não estiver disponível em anos antigos, fallback = `nome_completo + data_nascimento` normalizados, com flag `link_confiavel = false`.
- **Cargos em 2026:** `1` Presidente, `3` Governador, `5` Senador, `6` Deputado Federal, `7` Deputado Estadual, `8` Deputado Distrital. (Códigos TSE — confirmar no leiame 2026.)
- **Janela de mandato:** Governador/Presidente: `ano_eleicao+1` a `ano_eleicao+4`. Senador: 8 anos. Deputados: 4 anos.
- **Indicador com defasagem:** se o último ano disponível de um indicador for anterior ao fim do mandato, usar o último disponível e marcar `janela_incompleta = true`.

---

## 6. Features (com critérios de aceite)

Formato: **F-xx — nome** · *Prioridade* · Critérios de aceite (todos verificáveis por teste ou inspeção).

**F-01 — Ingestão TSE 2026** · P0
- Baixa S1, S2, S3, S5 para 2026; carrega em `raw_tse.*` com `_extracted_at`.
- Reexecutar não duplica linhas (carga substitui partição do ano).
- Teste: `count(*)` de candidatos 2026 ≥ 18.000 e todas as 27 UFs presentes.

**F-02 — Ingestão TSE histórico 1998–2022** · P0
- Mesmo padrão para 7 eleições gerais. Pode usar S12 (Base dos Dados) em vez de S1/S4 — decisão registrada em ADR.
- Teste: cada ano tem candidaturas a Presidente e Governador em todas as UFs.

**F-03 — Staging TSE unificado** · P0
- `stg_tse__candidaturas` com schema único apesar das variações de layout por ano.
- Testes dbt: `not_null` em `sq_candidato, ano_eleicao, cod_cargo, sg_uf`; `accepted_values` em `cod_cargo`; `unique` em `(sq_candidato, ano_eleicao)`.

**F-04 — Ingestão socioeconômica** · P0
- S6, S7, S8 no MVP; S9–S11 se couber. Cada indicador chega em formato longo (`indicador, uf, ano, valor`).
- Teste: nenhum indicador com gap > 2 anos consecutivos sem flag.

**F-05 — Marts (modelo estrela)** · P0
- Todas as tabelas da seção 5 materializadas como `table`.
- Testes de relacionamento (`relationships`) entre fatos e dimensões.
- `fct_mandato` cobre 100% dos governadores e presidentes eleitos 1998–2022.

**F-06 — Módulo "Durante o mandato"** · P0
- `fct_mandato_indicador` populado para todos os mandatos de Governador/Presidente com ≥ 1 indicador.
- Para cada candidato 2026 com mandato anterior, a página mostra: série temporal do indicador na UF, linha do Brasil, faixa sombreada do mandato, e o `delta_vs_brasil`.
- Texto fixo na página: *"Indicadores refletem o período; não medem o efeito do mandato."*

**F-07 — Power BI: hub e páginas** · P0
- Arquivo `bi/RadarBrasil.pbip` no repo.
- Página Visão Geral com navegação por botões para as demais.
- Toda página tem rodapé com fonte(s) e `_extracted_at`.
- Paleta neutra; cor de partido só quando o usuário liga um toggle.

**F-08 — Perfil de candidatos** · P1
- Filtros cruzados por cargo, UF, partido, gênero, cor/raça, faixa etária, instrução, reeleição.
- Distribuição de bens declarados (mediana, quartis, top-N com nome).

**F-09 — Metodologia** · P1
- Página no Power BI + `docs/METODOLOGIA.md` explicando fontes, janelas de mandato, limites da análise, e a regra de correlação ≠ causalidade.

**F-10 — Pipeline agendado** · P1
- GitHub Actions: `ingest → dbt run → dbt test` semanal, com falha bloqueando o merge.

**F-11 — Financiamento de campanha** · P2 (fase 2)
**F-12 — Resultados 2026** · P2 (fase 2, após 25/10)

---

## 7. Plano por fases e Tasks

### Fase 0 — Setup (1–2 dias)
- T-001 Criar repo, estrutura de pastas, `CLAUDE.md`, `.gitignore`, `pyproject.toml` (uv).
- T-002 Criar projeto GCP, datasets BigQuery, service account com escopo mínimo, secrets no GitHub.
- T-003 Inicializar dbt (`profiles.yml` via env vars).
- T-004 Definir `dim_uf` e `dim_cargo` como seeds dbt.
- **Aceite:** `dbt debug` verde localmente e no Actions.

### Fase 1 — TSE 2026 ponta a ponta (3–5 dias)
- T-101 `ingest/tse.py`: download com cache, unzip, leitura Latin-1, carga `raw_tse.candidatos` particionada.
- T-102 Mesmo para bens, complementar, vagas, coligações.
- T-103 `stg_tse__candidaturas` (só 2026 por enquanto) + testes.
- T-104 `dim_candidato`, `dim_partido`, `fct_candidatura` (2026).
- T-105 Power BI: conexão, página Visão Geral + Presidência + Governadores.
- **Aceite:** F-01, F-03 (parcial), F-07 (parcial). Dashboard mostra os candidatos a presidente e a governador de 2026 corretamente contra o DivulgaCandContas em amostra de 10 casos.

### Fase 2 — Histórico e mandatos (3–5 dias)
- T-201 Decidir e registrar ADR: Base dos Dados vs. CSV bruto para 1998–2022.
- T-202 Ingestão histórico + resultados agregados por UF.
- T-203 Unificar layouts em `stg` (mapa de colunas por ano em `ingest/layouts/tse_{ano}.yml`).
- T-204 `fct_mandato` + teste de cobertura de governadores/presidentes.
- T-205 Vinculação de pessoa entre anos (`cpf_hash` / fallback) + relatório de taxa de match.
- **Aceite:** F-02, F-03, F-05 (parcial). Lista de governadores eleitos por UF/ano bate com Wikipedia em amostra de 20.

### Fase 3 — Socioeconômico e "Durante o mandato" (4–6 dias)
- T-301 `ingest/ibge_sidra.py`, `ingest/ipeadata.py`, loaders para S8–S10.
- T-302 `fct_indicador_uf_ano` + `dim_indicador`.
- T-303 `fct_mandato_indicador` com comparadores Brasil e região.
- T-304 Página Power BI "Durante o Mandato" + "Contexto Socioeconômico".
- **Aceite:** F-04, F-05, F-06.

### Fase 4 — Polimento e publicação (2–3 dias)
- T-401 Página Metodologia + `docs/METODOLOGIA.md`.
- T-402 Perfil de candidatos completo (F-08).
- T-403 GitHub Actions semanal (F-10).
- T-404 Publish to web, README com prints, post de lançamento.
- **Aceite:** F-07, F-08, F-09, F-10. Deadline: antes de 04/10/2026.

### Fase 4.5 — Fotos (F-13, proposta) — 1 dia

- T-451 Criar bucket público `radar-brasil-fotos` em `US`, com acesso de leitura
  anônimo e *uniform bucket-level access*.
- T-452 `ingest/fotos.py`: baixa por UE, valida o padrão do nome, envia ao bucket,
  registra `sq_candidato → url` num NDJSON e carrega em `raw_tse.fotos`.
- T-453 `dim_candidato` ganha `url_foto` e `tem_foto`; dois testes dbt novos.
- T-454 Power BI: coluna marcada como *Image URL*, exibida na página principal.
- **Aceite:** F-13.

### Fase 5 — Pós-eleição (fase 2 do produto)
- F-11, F-12.

---

## 8. Estrutura do repositório

```
radar-brasil/
├── CLAUDE.md
├── SPEC.md                  ← este arquivo
├── README.md
├── pyproject.toml
├── Makefile                 # bootstrap, ingest, dbt, test
├── ingest/
│   ├── tse.py
│   ├── ibge_sidra.py
│   ├── ipeadata.py
│   ├── layouts/tse_{ano}.yml
│   └── common/ (download, bq_load, logging)
├── dbt/
│   ├── models/{raw_views,staging,marts}/
│   ├── seeds/
│   └── tests/
├── bi/
│   └── RadarBrasil.pbip
├── docs/
│   ├── METODOLOGIA.md
│   └── adr/
├── .github/workflows/pipeline.yml
└── data/                    # gitignored
```

---

## 9. Convenções para o Claude Code

- Nomes de colunas em `snake_case` pt-BR sem acento (`grau_instrucao`, não `grauInstrução`).
- Todo script de ingestão aceita `--ano` e `--dry-run`.
- Nenhum SQL fora de dbt; nenhum pandas em `marts` (transformação é no BigQuery).
- Commits em pt-BR, prefixo `feat:`, `fix:`, `data:`, `docs:`.
- Antes de marcar uma Task como concluída: `dbt test` verde e o critério de aceite da Feature checado.
- Ao encontrar coluna/layout inesperado no TSE: **não adivinhar** — abrir o `leiame.pdf` do ano e atualizar `layouts/tse_{ano}.yml`.
- Ao encontrar dado ausente em uma UF/ano: registrar em `docs/LACUNAS.md`, não preencher.

---

## 10. ADRs (registro de decisões)

| # | Decisão | Motivo | Status |
|---|---|---|---|
| ADR-001 | Power BI em vez de Looker Studio | Conector nativo BigQuery, `.pbip` versionável, melhor para portfólio corporativo | Aceita |
| ADR-002 | Import mode com tabelas agregadas | Evitar custo de query por interação no BigQuery | Aceita |
| ADR-003 | Localização do dataset BigQuery | `US` é compatível com Base dos Dados (US); `southamerica-east1` reduz latência. Se usar S12, `US`. | Pendente |
| ADR-004 | Base dos Dados para histórico | A decidir na T-201 | Pendente |
| ADR-005 | `cpf_hash` como chave de pessoa | Vincula anos sem expor CPF | Aceita |
| ADR-006 a ADR-011 | Ver `docs/adr/` | — | Aceitas |
| ADR-012 | Fotos em bucket público, não no BigQuery | Binário não pertence a um warehouse; o Power BI lê por URL | **Proposta** |

---

## 11. Perguntas em aberto

- O TSE 2026 já traz `cod_cargo` e layout iguais a 2022? (Verificar no leiame antes da T-101.)
- Quais séries do Ipeadata têm granularidade UF anual completa desde 1999?
- IDHM 2021 (atualização do Atlas) está disponível por UF em formato aberto?
- Publish to web do Power BI atende, ou vale embutir num site estático da DDI?

---

## 12. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Layout TSE muda entre anos | Alto | `layouts/tse_{ano}.yml` + testes de schema por ano |
| Indicadores com defasagem (PIB estadual sai com ~2 anos de atraso) | Médio | flag `janela_incompleta`, texto na tela |
| Leitura partidária do módulo "Durante o mandato" | Alto (reputacional) | Constituição 1 e 2; comparadores sempre visíveis; revisão de cada página com a pergunta "alguém pode ler isso como endosso?" |
| Estouro do free tier do BigQuery | Baixo | particionamento por ano; Power BI em Import; monitorar bytes processados |
| Prazo (1º turno em 04/10) | Alto | MVP = Fases 0–4; tudo mais é fase 2 |
