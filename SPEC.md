# Dossiê Eleitoral 2026
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
5. **Custo próximo de zero.** BigQuery dentro do free tier (10 GB storage / 1 TB query por mês). O site é **gerado uma vez por dia e servido estático** — zero query por visita, e escala por CDN sem teto (ADR-018).
6. **Versionado.** Código, SQL, modelos dbt e o gerador do site no GitHub. Sem dados brutos no repo (`.gitignore` em `data/`).
7. **LGPD/ética.** Dados de candidatos são públicos por lei, mas o projeto não expõe CPF nem endereço, e não cruza com dados de terceiros que não sejam agregados.

---

## 1. Visão e problema

**Uma frase:** um hub analítico que mostra *quem* são os candidatos das eleições gerais de 2026 (Presidente, Governador, Senador, Deputado Federal, Deputado Estadual/Distrital) e *em que contexto socioeconômico* concorrem — incluindo o que aconteceu nos indicadores de sua UF/país durante mandatos anteriores de quem tenta reeleição ou já governou.

**Por que existe:** peça de portfólio da Data Duba Intelligence (DDI) demonstrando pipeline completo (ingestão → BigQuery → dbt → site público) sobre dados públicos brasileiros, com gancho de atualidade (eleições 2026, 1º turno em 04/10/2026). O produto público chama-se **Dossiê Eleitoral**.

**Público:** recrutadores e potenciais clientes da DDI (primário); jornalistas de dados e eleitores curiosos (secundário).

---

## 2. Escopo

### 2.1 Dentro do escopo (MVP — entrega antes do 1º turno)
- Candidatos 2026 de todos os cargos em disputa, todas as UFs.
- Perfil: cargo, UF, partido, coligação/federação, gênero, cor/raça, idade, grau de instrução, ocupação, situação da candidatura, reeleição (sim/não), bens declarados.
- **Foto oficial de urna de cada candidato de 2026** (F-13).
- Histórico: eleições gerais 1998–2022 (candidaturas e resultados) para montar *"quem já ocupou o cargo"*.
- Contexto socioeconômico por UF e Brasil: PIB e PIB per capita, população, desemprego (PNAD Contínua), IDHM, mortalidade infantil, IDEB, homicídios (Atlas da Violência/IPEA), receita/despesa pública (SICONFI).
- Módulo *"Durante o mandato"*: para candidatos que foram Governador ou Presidente em mandato anterior, série dos indicadores da UF/Brasil no período do mandato vs. comparadores.
- Dossiê Eleitoral com páginas: Candidatos → Presidência → Governadores → Senado → Câmara → Assembleias → Contexto Socioeconômico → Durante o Mandato → Metodologia/Fontes.

### 2.2 Fora do escopo (explicitamente)
- Propostas de governo (texto livre) — fase futura.
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
| S4 | TSE — `votacao_candidato_munzona_{ano}.zip` | Votos por candidato/município/zona | CSV, grande (GBs) | Só 1998–2022 no MVP; agregar antes de subir ao BigQuery |
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
| S15 | Câmara — API de Deputados | Deputados em exercício | REST JSON | 513 em 28/08/2026 |
| S16 | Senado — API de Senadores | Senadores em exercício | REST XML | 81 em 28/08/2026. **Não publica CPF** — daí o casamento por nome + nascimento (ADR-014) |
| S17 | Câmara — arquivos em lote de proposições | Proposições e autorias, 2023–2026 | CSV anual | 296.962 proposições após filtrar `proponente = 1` |
| S18 | TSE — prestação de contas eleitorais | Receitas e despesas de campanha | ZIP de CSV por UF | 43.610 receitas e 54.019 despesas em 28/08/2026, sobre 7.722 candidaturas. **Traz CPF de doador em texto puro** — hasheado na ingestão (ADR-020). Cobertura cresce até depois de 04/10 |

**Regra:** cada fonte tem um script/idempotente em `ingest/` que baixa, valida hash, e carrega em `raw_*`. A data de extração é gravada em coluna `_extracted_at`.

---

## 4. Arquitetura

```
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   ┌───────────────┐
│ Fontes       │──▶│ ingest/ (py) │──▶│ BigQuery         │──▶│ Site estatico │
│ TSE IBGE IPEA│   │ download +   │   │ raw → stg → marts│   │ Import mode   │
│ basedosdados │   │ load raw     │   │ (dbt)            │   │ HTML + JSON   │
└──────────────┘   └──────────────┘   └──────────────────┘   └───────────────┘
                          │                    ▲
                          └── GitHub Actions ──┘ (agendado + manual)
```

- **Linguagem:** Python 3.11+, `uv` para dependências.
- **Warehouse:** BigQuery, projeto `radar-brasil-ddi` (o *project id* do GCP é imutável e não acompanhou o rename — ver ADR-026), datasets `raw_tse`, `raw_ibge`, `raw_ipea`, `stg`, `marts`. Localização `southamerica-east1` ou `US` (decidir — ver ADR-003).
- **Transformação:** dbt-core + dbt-bigquery. Testes de schema obrigatórios em toda tabela de `marts`.
- **Orquestração:** GitHub Actions (cron semanal até a eleição; manual depois). Sem Airflow no MVP.
- **Publicação:** site estático gerado por script Python a partir de `marts`, hospedado com CDN. Sem servidor de aplicação: o dado muda uma vez por dia (ADR-018).
- **Camadas de dados:**
  - `raw_*`: cópia fiel da fonte, tipos STRING, particionado por `ano_eleicao` quando aplicável.
  - `stg_*`: tipagem, renomeação para snake_case em pt-BR, deduplicação, padronização de códigos (UF, cargo, partido).
  - `marts`: modelo estrela consumido pelo gerador do site.

---

## 5. Modelo de dados (`marts`)

### Dimensões
- `dim_candidato` — `sq_candidato` (chave TSE por eleição), `nome_urna`, `nome_completo`, `cpf_hash` (SHA-256 para linkar entre anos sem expor CPF), `genero`, `cor_raca`, `data_nascimento`, `grau_instrucao`, `ocupacao`, `url_foto` e `tem_foto` (F-13).
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

**F-07 — Dossiê Eleitoral: site estático gerado do lake** · P0
> Reescrita em 28/08/2026. Ver [ADR-018](docs/adr/ADR-018-site-estatico-em-vez-de-bi.md).
- Gerador em Python lê `marts` e escreve HTML + JSON estáticos, na esteira diária.
- **Uma URL por candidato** — compartilhável e indexável pelo Google. É o que a
  publicação em iframe impedia, e o motivo de a ferramenta de BI ter caído.
- Sete páginas por cargo, layout de dossiê: retrato, perfil declarado, trajetória
  eleitoral, plano de governo e alterações registradas.
- Toda página tem rodapé com fonte(s) e `_extracted_at`.
- Paleta neutra; **cor de partido nunca como padrão** — só sob escolha explícita
  de quem lê.
- Sem barra de pontuação, sem nota, sem veredito automático: a ficha é registro,
  não avaliação (Constituição §0.1).

**F-08 — Perfil de candidatos** · P1
- Filtros cruzados por cargo, UF, partido, gênero, cor/raça, faixa etária, instrução, reeleição.
- Distribuição de bens declarados (mediana, quartis, top-N com nome).

**F-09 — Metodologia** · P1
- Página no site + `docs/METODOLOGIA.md` explicando fontes, janelas de mandato, limites da análise, e a regra de correlação ≠ causalidade.

**F-10 — Pipeline agendado** · P1
- GitHub Actions: `ingest → dbt run → dbt test` semanal, com falha bloqueando o merge.

**F-11 — Financiamento de campanha** · P1 · **Implementada em 28/08/2026**

> Fonte nova (S18). Ver [ADR-020](docs/adr/ADR-020-financiamento-de-campanha.md).

**Por que saiu da fase 2:** a prestação de contas só fica *completa* depois da
eleição, mas já está *substantiva*: R$ 3,59 bilhões declarados sobre 7.722
candidaturas em 28/08/2026. Esperar o número final teria custado a única fonte que
liga uma candidatura a quem a sustenta.

**Alcance real:** 43.610 lançamentos de receita e 54.019 de despesa contratada.
Conferido contra o TSE ao centavo (Regra 6): a candidatura de Luiz Inácio Lula da
Silva soma R$ 35.267.670,96 no pipeline e R$ 35.267.670,96 na página oficial.

**O que NÃO entra, de propósito:**
- **CPF de doador.** O arquivo traz em texto puro; a ingestão substitui por HMAC
  antes de gravar. CNPJ fica legível — identifica empresa, não pessoa.
- **Ranking por valor arrecadado.** Arrecadar muito não é mérito nem demérito, e
  lista de político ordenada por dinheiro é placar (Constituição §0.1).
- **Zero fabricado.** Quem não declarou não aparece com R$ 0,00 — aparece como
  *"prestação ainda não entregue"*, que é outra coisa.

**F-12 — Resultados 2026** · P2 (fase 2, após 25/10)

---

**F-19 — Atividade legislativa de mandatos anteriores** · P1 · **Implementada em 30/08/2026**

> Ver [ADR-024](docs/adr/ADR-024-atividade-de-mandatos-anteriores.md).

**Por que entra:** 118 dos 529 majoritários de 2026 já foram deputados federais,
e só 48 tinham atividade na ficha. As proposições dos outros 70 existiam desde
2003; faltava a identidade — a ponte só conhecia quem está em exercício hoje.

**Alcance real:** ponte de 513 para 1.992 parlamentares (100% casados por CPF),
período de 2023-2026 para 2003-2026, 817.822 proposições, e **117 de 118**
majoritários possíveis com atividade.

**O que NÃO entra, de propósito:** taxa de presença. A API não publica, e derivar
de eventos confunde falta com comissão, missão oficial e licença médica.

**Distinção que a feature obrigou a criar:** atividade registrada na Câmara não
prova mandato de deputado. Senador apresenta emenda a MP na comissão mista e a
Câmara registra a autoria. A ficha marca esses períodos como *sem mandato de
deputado* em vez de rotulá-los como legislatura.

---

**F-20 — Votos e presença em plenário** · P1 · **Implementada em 30/08/2026**

> Fonte nova (S19). Ver [ADR-025](docs/adr/ADR-025-plenario-e-chapas.md).

**Alcance:** 2003-2026, 2.024 deputados, 1,9 milhão de votações e 2,5 milhões de
presenças — agregados na ingestão para (deputado, ano), o que mantém a tabela em
13 mil linhas em vez de dezenas de milhões.

**O que NÃO entra:** taxa de presença. A fonte diz onde o parlamentar esteve, não
a quantos eventos deveria ter ido, e sem denominador não existe percentual
honesto. Fica o **volume**, com plenário separado de comissão.

---

**F-21 — Chapa: vice e suplentes** · P1 · **Implementada em 30/08/2026**

> Fonte nova (S14b). Ver [ADR-025](docs/adr/ADR-025-plenario-e-chapas.md).

**Por que entra:** vice e suplente já estavam no lake com candidatura própria —
13 vice-presidentes, 203 vice-governadores, 661 suplentes. O que não existe no
pacote em lote do TSE é a **chapa**: nada dizia que Alckmin concorre com Lula.

**Alcance real:** 889 vínculos, 887 resolvidos. Os 2 restantes são suplentes
registrados depois da última publicação em lote do TSE (L-23).

---

**F-18 — Ficha própria para as candidaturas proporcionais** · P1 · **backlog, aprovada em 29/08/2026**

**Por que entra.** O projeto foi mostrado a pessoas reais e a falta mais citada
foi esta: quem decide o voto para deputado enfrenta 1.126 nomes só em São Paulo,
e é justamente aí que uma ficha ajuda mais — não menos. Hoje os 529 majoritários
têm página própria e as 20.765 candidaturas proporcionais têm apenas listagem.

**O contra-argumento, e por que ele perde.** Vinte mil páginas com poucos campos
distintos é o padrão que buscadores classificam como conteúdo raso, e o risco não
é penalidade: é o site inteiro passar a ser lido como de baixa qualidade. O
critério que decide, porém, não é ranqueamento — é **utilidade pública**
(Constituição §0). Um site de consulta serve quem chega por link direto e por
compartilhamento, e ficha sem URL própria não é compartilhável.

**Alcance.** Uma página por candidatura proporcional (~20.765 em 2026), no mesmo
formato da dos majoritários: foto oficial, perfil declarado, legenda completa
(federação, coligação e composição), número na urna, trajetória eleitoral,
prestação de contas e — para quem tem — atividade legislativa.

**O que muda na engenharia, e não é pouco:**
- a geração passa de ~740 para ~21 mil páginas;
- o envio por FTP deixa de caber numa execução: hoje são 790 arquivos em 13
  minutos, e 21 mil no mesmo ritmo passariam de cinco horas. **Exige sincronização
  incremental** — enviar só o que mudou, comparando hash contra um manifesto no
  servidor. É o item que precisa ser resolvido antes de qualquer outro;
- o `sitemap.xml` passa de 738 para ~21 mil URLs, e deve ser dividido em índice
  mais sitemaps por cargo e UF (o limite por arquivo é 50 mil URLs, mas arquivos
  menores são rastreados melhor).

**O que NÃO muda.** Nenhum ranking, nenhuma nota, nenhum indicador
socioeconômico atribuído a deputado — o vínculo entre um parlamentar e um número
regional é fraco demais para ir à tela (SPEC §2.2), e isso vale igualmente aqui.

---


---

**F-15 — Ponte de identidade com Câmara e Senado** · P1 · **Implementada em 28/08/2026**

> Fonte nova (S15, S16). Ver [ADR-014](docs/adr/ADR-014-ponte-legislativo.md).

**Por que entra:** 93% das candidaturas de 2026 são para cargos legislativos, e a
ficha dessas pessoas hoje só tem perfil declarado e trajetória eleitoral. Sem esta
ponte, nada do que o parlamentar fez no mandato chega ao painel.

**Alcance real:** 513 deputados casados por CPF (100%) e 81 senadores casados por
nome + data de nascimento, marcados com `casamento_confiavel = false` porque o
Senado não publica CPF. Homônimo com a mesma data de nascimento **não** recebe
`id_pessoa` — vira `metodo_id_pessoa = 'ambiguo'`.

---

**F-16 — Atividade legislativa na Câmara** · P1 · **Implementada em 28/08/2026**

> Fonte nova (S17). Ver [ADR-015](docs/adr/ADR-015-atividade-legislativa.md).

**Por que entra:** é a única prestação de contas defensável para um deputado. O
vínculo entre um parlamentar e um indicador socioeconômico regional é fraco demais
para ser mostrado (SPEC §2.2), mas o que ele propôs é ato próprio dele.

**O que NÃO entra, de propósito:** taxa de aprovação. Aprovar depende de estar na
base do governo, não do mérito do texto — a taxa puniria a oposição por ser
oposição, em qualquer governo, e viraria placar (Constituição §0.1).

**Alcance real:** 296.962 proposições de 710 deputados na legislatura 2023-2026,
já filtradas por `proponente = 1` (21,4% das linhas de autoria eram apoio) e
separadas em cinco classes, porque projeto de lei e requerimento de retirada de
pauta não são a mesma coisa.

---

**F-14 — Proposta de governo dos candidatos majoritários** · P1 · **Implementada em 28/08/2026**

> Fonte nova (S14). O SPEC §2.2 excluía "propostas de governo (texto livre)"; esta
> feature **não** traz o texto — traz a existência e o link para a fonte oficial.
> Ver [ADR-013](docs/adr/ADR-013-proposta-de-governo.md).

**Por que entra:** a página do candidato precisa dizer se ele apresentou proposta.
Sem isso, a ficha de um candidato a governador fica igual à de um a deputado, que
não tem essa obrigação.

**Alcance real:** a Lei 9.504/97 (art. 11, §1º, IX) exige a proposta de candidatos
a **Prefeito, Governador e Presidente**. Senador é majoritário mas **não** consta
da lista — e a medição confirma: 0 de 318 senadores têm proposta, contra 193 de
198 governadores. Em 2026 a obrigação alcança **211 de 20.769 candidaturas (1,0%)**.

Critérios de aceite:

- `fct_candidatura` distingue **três** estados, e a tela também: `não se aplica a
  este cargo` (proporcionais), `apresentou` e `não consta`. Campo em branco é
  proibido — vazio se lê como omissão do candidato.
- `proposta_obrigatoria` é derivada do cargo (a lei), não do dado.
- Teste dbt: nenhuma candidatura sem obrigação legal com `tem_proposta_governo = true`.
- Teste dbt: nenhuma candidatura com proposta sem `url_proposta_oficial`.
- Nenhum PDF é baixado ou re-hospedado (ADR-013).

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
- ~~T-105 Power BI: conexão, página Visão Geral + Presidência + Governadores.~~ → **T-105 Gerador do site: páginas Candidatos + Presidência + Governadores** (ADR-018).
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
- T-304 Páginas "Durante o Mandato" e "Contexto Socioeconômico" no site.
- **Aceite:** F-04, F-05, F-06.

### Fase 4 — Polimento e publicação (2–3 dias)
- T-401 Página Metodologia + `docs/METODOLOGIA.md`.
- T-402 Perfil de candidatos completo (F-08).
- T-403 GitHub Actions semanal (F-10).
- T-404 Publish to web, README com prints, post de lançamento.
- **Aceite:** F-07, F-08, F-09, F-10. Deadline: antes de 04/10/2026.

### Fase 4.5 — Fotos (F-13) — concluída em 28/08/2026

- T-451 Criar bucket público `dossie-eleitoral-fotos` em `US`, com acesso de leitura
  anônimo e *uniform bucket-level access*.
- T-452 `ingest/fotos.py`: baixa por UE, valida o padrão do nome, envia ao bucket,
  registra `sq_candidato → url` num NDJSON e carrega em `raw_tse.fotos`.
- T-453 `dim_candidato` ganha `url_foto` e `tem_foto`; dois testes dbt novos.
- T-454 Retrato do candidato na ficha, lido por URL do bucket público.
- **Aceite:** F-13.

### Fase 4.6 — Proposta de governo (F-14) — concluída em 28/08/2026

- T-461 `ingest/propostas.py`: consulta a API do DivulgaCandContas por candidatura
  majoritária, identifica os arquivos `codTipo = 5` e carrega em `raw_tse.propostas`.
- T-462 `stg_tse__propostas`; `fct_candidatura` ganha os cinco campos da F-14.
- T-463 Dois testes dbt novos + rótulo de três estados na ficha (apresentou / não apresentou / não exigido).
- **Aceite:** F-14.

### Fase 4.7 — Legislativo (F-15, F-16) — concluída em 28/08/2026

- T-471 `ingest/legislativo.py`: coleta os 513 deputados e 81 senadores em
  exercício e carrega `raw_legislativo.parlamentares` com as duas chaves de
  identidade.
- T-472 `ingest/proposicoes.py`: arquivos anuais em bloco da Câmara, filtrados por
  `proponente = 1` e classificados por tipo, em `raw_legislativo.proposicoes`.
- T-473 `stg_camara__parlamentares`, `stg_camara__proposicoes`, `dim_parlamentar`
  (resolve `id_pessoa` contra o TSE) e `fct_atividade_legislativa`.
- T-474 Três testes dbt novos: cobertura da ponte por Casa, recusa de homônimo
  ambíguo e teto para a classe residual.
- **Aceite:** F-15, F-16.

### Fase 5 — Pós-eleição (fase 2 do produto)
- F-11, F-12.

---

## 8. Estrutura do repositório

```
dossie-eleitoral/
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
| ADR-001 | Power BI em vez de Looker Studio | Conector nativo BigQuery, `.pbip` versionável | **Substituída pela ADR-018** |
| ADR-002 | Import mode com tabelas agregadas | Evitar custo de query por interação no BigQuery | Aceita (levada ao extremo pela ADR-018) |
| ADR-003 | Localização do dataset BigQuery | `US` é compatível com Base dos Dados (US); `southamerica-east1` reduz latência. Se usar S12, `US`. | Pendente |
| ADR-004 | Base dos Dados para histórico | A decidir na T-201 | Pendente |
| ADR-005 | `cpf_hash` como chave de pessoa | Vincula anos sem expor CPF | Aceita |
| ADR-006 a ADR-011 | Ver `docs/adr/` | — | Aceitas |
| ADR-012 | Fotos em bucket público, não no BigQuery | Binário não pertence a um warehouse; a ficha lê por URL | Aceita |
| ADR-013 | Proposta de governo: existência + link, sem re-hospedar PDF | Credibilidade da fonte, cópia envelhece | **Emendada pela ADR-019** — o download não exigia engenharia reversa, e o link do TSE quebrou |
| ADR-014 | Ponte de identidade com Câmara e Senado | Câmara publica CPF (casamento exato); Senado não, e a diferença viaja no dado | Aceita |
| ADR-015 | Atividade legislativa por classe, sem taxa de aprovação | Aprovação depende de estar na base do governo, não do mérito — seria placar | Aceita |
| ADR-016 | Intermediário TLS do INEP versionado em `certs/` | O servidor omite um elo da cadeia; a raiz sempre foi confiável. Destrava o IDEB | Aceita |
| ADR-017 | Orçamento federal pelo RTN, não pela DCA | A receita da DCA inclui operações de crédito (45% da União em 2020); o resultado tendia a zero por identidade contábil | Aceita |
| ADR-020 | Financiamento de campanha, com o CPF do doador fora | O TSE publica CPF de doador em texto puro; o nome basta para prestar contas, o número só acrescenta risco | Aceita |
| ADR-021 | O nome que o certificado do FTP precisa cobrir | A Hostinger apresenta certificado de `*.hstgr.io`, nao do dominio do cliente; verificar contra o nome real mantem a validacao completa, e fixar o certificado quebraria na renovacao | Aceita |
| ADR-022 | Fonte indisponivel nao derruba a carga diaria | Timeout de API publica e' instabilidade; 404 e' fonte que mudou. Tratar os dois igual faria a serie parar de atualizar em silencio ou o job morrer a cada blip | Aceita |
| ADR-023 | Resultado apurado dos votos, onde o TSE nao publica | O `COALESCE(...,FALSE)` transformava ausencia em "nao eleito" e publicou que Lula perdeu em 2006; tres estados, e apuracao aritmetica so' para cargo majoritario | Aceita |

| ADR-035 | A receita estadual passa a ser a Receita Corrente Líquida | A conferência achou que faltava descontar as transferências constitucionais (R$ 23,8 bi em MG 2023) e que a declaração das deduções muda entre estados e anos; a RCL é padronizada por lei. O resultado orçamentário saiu | Aceita |
| ADR-034 | Atividade legislativa do Senado, com o mesmo rigor da Câmara | `ordem = 1` como equivalente do `proponente`, validado em 48 comparações contra a flag oficial do endpoint descontinuado; classes mapeadas pela lista oficial de siglas, não pelo formato | Aceita |
| ADR-033 | Página de quem financia as campanhas | 23.532 repasses numa linha por financiador × candidatura; publicar todas as pessoas físicas foi decisão explícita do dono do projeto, com o número de exposição na mão. Sem CPF | Aceita |
| ADR-032 | Ficha própria para o vice de presidente e de governador | 216 candidaturas que só existiam como cartão na ficha do titular; Alckmin tem três mandatos de governador que não tinham onde aparecer. Suplente de senador fica de fora | Aceita |
| ADR-031 | A ausência de um indicador é dita na ficha, não só respeitada | Omitir a linha sem dizer que omitiu é indistinguível de esconder; o rodapé de cada mandato passa a listar o que falta e por quê, derivado do alcance real da série | Aceita |
| ADR-030 | Desocupação vem da série anual oficial; rendimento fica no "efetivamente recebido" | A média dos quatro trimestres dava 6,85% contra os 6,6% publicados — número que não existia em publicação nenhuma. Avisar que diverge não é o mesmo que publicar o certo | Aceita |
| ADR-029 | O indicador tem de medir o ente que a pessoa chefiou | A soma do orçamento dos 27 estados aparecia na ficha de um presidente rotulada "Despesa do estado"; catálogo passa a declarar `ente_medido`, o dbt filtra por cargo e o rótulo segue o ente governado | Aceita |
| ADR-028 | "Durante mandatos anteriores" separa por mandato | O título nomeava o mandato da primeira linha para uma tabela que juntava todos — falso para 57 dos 129 candidatos com o bloco; ordem alfabética passa a ser a do nome exibido, não a do banco | Aceita |
| ADR-027 | Queda de conexão não derruba a publicação inteira | 793 arquivos numa sessão FTP; o servidor corta a conexão a cada ~100. Reconecta e continua do mesmo arquivo, mas `error_perm` (5xx) segue falhando alto | Aceita |
| ADR-026 | Tudo passa a se chamar Dossiê Eleitoral | Três nomes em circulação às vésperas da divulgação para imprensa, um deles na URL de toda foto do site; o *project id* do GCP e o salt público não acompanham, por serem imutável e chave | Aceita |
| ADR-025 | Votações, presença em plenário e a chapa titular–vice | Agregar por (deputado, ano) na ingestão troca milhões de linhas por 13 mil; da chapa guarda-se só o PAR, nunca atributo do vice | Aceita |
| ADR-024 | Atividade de mandatos anteriores | Ponte de identidade por CPF entre legislaturas, cobertura de 48 para 117 majoritários | Aceita |
| ADR-019 | Texto integral dos planos de governo | O endpoint certo do TSE estava no bundle do próprio app; 201 de 206 planos transcrevem, 19,3 mi de caracteres | Aceita |
| ADR-018 | Site estático gerado do lake, em vez de ferramenta de BI | *Publish to web* não tem layout mobile, URL por candidato nem indexação; e 20 mil candidatos que mudam 1x/dia são geração estática, não consulta ao vivo | Aceita |

---

## 11. Perguntas em aberto

- ~~A taxa de desocupação do site não é a que o IBGE publica.~~
  **Respondida em 01/09/2026 (ADR-030):** trocada para a série anual oficial (SIDRA
  t/4562). Confere ano a ano — 6,6% em 2024.
- ~~`RENDIMENTO_MEDIO` usa a série "efetivamente recebido"...~~
  **Respondida em 01/09/2026 (ADR-030):** mantém-se o efetivamente recebido, e a tela
  passa a nomear a série. A base de deflação, que anda a cada divulgação, também está dita.
- ~~O trio do SICONFI nunca foi conferido contra publicação externa.~~
  **Respondida em 03/09/2026 (ADR-035):** conferido pela estrutura, não pelo agregado — e
  achou um erro. A receita virou Receita Corrente Líquida; o resultado saiu (L-26).
- O TSE 2026 já traz `cod_cargo` e layout iguais a 2022? (Verificar no leiame antes da T-101.)
- Quais séries do Ipeadata têm granularidade UF anual completa desde 1999?
- ~~IDHM 2021 (atualização do Atlas) está disponível por UF em formato aberto?~~
  **Respondida em 28/08/2026:** não nesta série. O Ipeadata publica `ADH_IDHM` com
  1991, 2000 e 2010 — sem 2021. O IDHM entrou como linha de base histórica (L-04).
- **O IDEB de ENSINO MÉDIO deve virar indicador próprio?** O arquivo do INEP já
  traz as três etapas e o código lê qualquer uma — falta só uma entrada de
  catálogo. O ensino médio é majoritariamente **estadual**, portanto o mais
  próximo da responsabilidade de um governador; hoje o projeto ingere apenas anos
  finais do fundamental, que é o que o §3 (S8) especificava. Idem anos iniciais,
  que são majoritariamente municipais e servem melhor à página de Prefeito de 2028.
- ~~Publish to web do Power BI atende, ou vale embutir num site estático da DDI?~~
  **Respondida em 28/08/2026:** site estático. O *Publish to web* não suporta
  layout mobile, não dá URL por candidato e não é indexável — os três canais pelos
  quais um produto público de fato circula. Ver ADR-018.

---

## 12. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Layout TSE muda entre anos | Alto | `layouts/tse_{ano}.yml` + testes de schema por ano |
| Indicadores com defasagem (PIB estadual sai com ~2 anos de atraso) | Médio | flag `janela_incompleta`, texto na tela |
| Leitura partidária do módulo "Durante o mandato" | Alto (reputacional) | Constituição 1 e 2; comparadores sempre visíveis; revisão de cada página com a pergunta "alguém pode ler isso como endosso?" |
| Estouro do free tier do BigQuery | Baixo | particionamento por ano; site gerado 1x/dia (zero query por visita); monitorar bytes processados |
| Prazo (1º turno em 04/10) | Alto | MVP = Fases 0–4; tudo mais é fase 2 |
