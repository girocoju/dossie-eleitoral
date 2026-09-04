# Estado das Tasks

> Atualizado em **2026-08-27**. Fonte da verdade sobre o que esta' feito.
> Convencao: ✅ feito e verificado · 🟡 codigo pronto, execucao pendente · ⬜ nao iniciado
>
> O BigQuery esta' configurado (o identificador do projeto vive em `.env` e nas
> variaveis do Actions, nao aqui), modo sandbox, datasets
> em `US`. As credenciais locais sao ADC (`gcloud auth application-default login`) —
> nao ha' chave de service account em disco. A configuracao local fica em `.env`
> (gitignored), incluindo o `RADAR_CPF_SALT`.

## Fase 0 — Setup

| Task | Estado | Nota |
|---|---|---|
| T-001 Repo, estrutura, `CLAUDE.md`, `.gitignore`, `pyproject.toml` | ✅ | Repo Git proprio inicializado na pasta do projeto |
| T-002 Projeto GCP, datasets, credenciais | ✅ | Projeto com faturamento ativo, orcamento de R$ 20 com alertas. Credencial local via ADC, sem chave de service account |
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
| T-105 Dossie Eleitoral: gerador do site | ✅ | `scripts/gerar_site.py` + `render_site.py`: 960 paginas no ar em `datadubaintel.com/dossie-eleitoral`. O texto "gerador a escrever" ficou parado uma semana depois de o gerador existir |

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
| T-202 Ingestao do historico + resultados por UF | ✅ | 8 anos: 180.718 candidaturas, 509.136 bens, **142.086 linhas de votacao** (L-02 fechada) |
| T-203 Mapa de colunas por ano em `layouts/tse_{ano}.yml` | ✅ | **8 anos conferidos** contra os arquivos reais (L-01 fechada) |
| T-204 `fct_mandato` + teste de cobertura | ✅ | 11.777 mandatos, 1999–2026. 7 por eleicao suplementar, 7 interrompidos |
| T-205 Vinculacao de pessoa + relatorio de taxa de match | ✅ | **Medido em 02/09/2026**: vinculacao por CPF em 96,9% (1998) a 100% (2006, 2010, 2026) das candidaturas. O fallback por nome+nascimento so pesa em 1998 (445) e 2002 (113); sem chave nenhuma, no maximo 1,3% (2002). L-10 fechada |

## Fase 3 — Socioeconomico e "Durante o mandato"

| Task | Estado | Nota |
|---|---|---|
| T-301 `ingest/ibge_sidra.py`, `ingest/ipeadata.py` | ✅ | 4 series conferidas contra a API real; S8–S10 em [LACUNAS](LACUNAS.md) |
| T-302 `fct_indicador_uf_ano` + `dim_indicador` | ✅ | 3.360 linhas, 5 indicadores, **0 sem comparador nacional** |
| T-303 `fct_mandato_indicador` com comparadores | ✅ | 818 linhas: 197 mandatos de Presidente/Governador x 5 indicadores |
| T-304 Paginas "Durante o Mandato" e "Contexto Socioeconomico" | ✅ | Entregue pelo SITE, nao pelo Power BI (ADR-018): o bloco "Durante mandatos anteriores" esta em cada ficha, separado por mandato (ADR-028) e com a ausencia de indicador dita (ADR-031) |

**Indicadores em `fct_indicador_uf_ano`** — 9 series, 4.307 linhas:

| Indicador | Periodo | Fonte |
|---|---|---|
| Mortalidade infantil | 2000–2016 | IBGE t/3834 |
| PIB | 2002–2023 | IBGE t/5938 |
| PIB per capita | 2002–2022 | derivado |
| Populacao (estimativa) | 2001–2025 | IBGE t/6579 |
| Populacao (Censo) | 2022 | IBGE t/4709 |
| Desocupacao | 2012–2025 | PNAD Continua |
| Homicidios | 1980–2024 | Atlas da Violencia |
| **Receita estadual** | **2015–2025** | **SICONFI/DCA** |
| **Despesa estadual** | **2015–2025** | **SICONFI/DCA** |
| **Resultado orcamentario** | **2015–2025** | **derivado** |

| **IDEB (anos finais, rede publica)** | **2005–2025** | **INEP** |
| **IDHM** | **1991/2000/2010** | **Ipeadata (Atlas)** |
| **IPCA** | **1980–2025** | **SIDRA t/1737** |
| **Selic** | **1980–2025** | **Ipeadata** |

Mais o orcamento FEDERAL, que vem de fonte propria: `RECEITA_LIQUIDA_UNIAO`,
`DESPESA_PRIMARIA_UNIAO` e `RESULTADO_PRIMARIO_UNIAO`, do **RTN do Tesouro**,
**1997–2025**.

Ate' 28/08/2026 o federal vinha da DCA como o estadual, e estava errado: a receita
da DCA inclui operacoes de credito (45% do total da Uniao em 2020), entao a conta
tendia a zero por identidade contabil e a serie chegou a mostrar "superavit de
R$ 635 bi" em 2025, onde havia deficit de 61,7 bi. Ver L-22 e ADR-017.

O federal e o estadual NAO se somam nem se comparam: conceitos diferentes, entes
diferentes, metodologias diferentes.

**Zero linhas sem comparador nacional.**

## Votacao (L-02 e L-19 fechadas)

| Tabela | Linhas | Grao |
|---|---:|---|
| `raw_tse.votacao` | 142.086 | candidatura x turno x UF |
| `marts.fct_votacao_uf` | 142.086 | + nome, partido, % do total do candidato |
| `marts.fct_votacao_municipio` | **752.232** | candidatura x turno x municipio, so' Presidente e Governador |

6.387 municipios cobertos. Validado contra a historia: FHC 35.936.382 no 1o turno
de 1998.

## Fase 4 — Polimento e publicacao

| Task | Estado | Nota |
|---|---|---|
| T-401 Pagina Metodologia + `docs/METODOLOGIA.md` | ✅ | Documento escrito; pagina do relatorio a montar |
| T-402 Perfil de candidatos completo (F-08) | ✅ | Entregue pelo SITE (ADR-018): bloco "Perfil declarado ao TSE" em 960 fichas, mais as listagens filtraveis por UF e partido. "Filtros a montar no Desktop" era Power BI Desktop, aposentado em 28/08 |
| T-403 Atualizacao diaria (F-10) | OK | Roda na maquina do usuario pelo `atualizar.bat` no Agendador de Tarefas do Windows; as fontes ANUAIS entram sozinhas aos domingos. O workflow perdeu o `schedule` e continua como rede de seguranca, por push e disparo manual |
| T-416 `publicar.bat` e a ordem de envio | OK | 03/09/2026: `dossie.css` sobe em ordem alfabetica DEPOIS de `candidato/`, e na publicacao da F-18 isso deixou 20 mil fichas novas no ar apontando para uma folha que ainda nao existia — 404 no CSS, site sem estilo, num site publico. O que as paginas dependem passa a subir primeiro. E a publicacao ganhou .bat proprio, com log linha a linha: a saida da F-18 ficou presa num buffer ate' o fim, sem como acompanhar |
| T-423 Um publicador por vez (ADR-047) | OK | 04/09/2026: quatro falhas de publicacao em duas noites, cada uma com sintoma diferente, e as correcoes todas necessarias — nenhuma era a causa. A causa era o workflow publicar A CADA PUSH enquanto o `atualizar.bat` publica da maquina: nove publicacoes de 20 mil arquivos numa noite, cada uma cancelada pela seguinte NO MEIO DO ENVIO. Push passa a parar em `verificar`; carga e publicacao so' por disparo manual; e a publicacao trava o servidor enquanto roda. O aviso ja' estava escrito no cabecalho do workflow desde 31/08, e so' considerava o AGENDAMENTO |
| T-422 Emendas parlamentares (F-27 / ADR-046) | OK | 04/09/2026: o Portal IGNORA o ano no endereco — os treze anos devolvem o mesmo sha256, e a primeira carga somou 1.228.019 linhas que eram treze copias de 94.463. Nada falharia: a carga terminaria verde e toda soma sairia x13. Denunciou a contagem identica em todos os anos |
| T-421 Residuo de envio interrompido (ADR-045) | OK | 04/09/2026: o servidor deixa um oculto `.in.<nome>.` quando a transferencia morre, e o 550 seguinte derrubou a publicacao depois de 6.200 arquivos. Reconhecido e removido — com validacao do caminho, para que um servidor hostil nao consiga mandar apagar outra coisa |
| T-420 Comissoes da Camara (F-26 / ADR-044) | OK | 04/09/2026: tres armadilhas da fonte. (1) `/deputados/{id}/orgaos` sem data devolve UM vinculo para Arthur Lira, que presidiu a Casa — com a janela, 41. (2) o catalogo padrao de orgaos nao tem MESA, PRESI nem COETICA; resolver o que falta levou os vinculos classificados de 545 para 1.060 na mesma amostra. (3) o tipo 15 chama-se "COORDENADORIA DA MULHER" e agrupa a Bancada Negra — classificar pelo NOME diria que sao a mesma coisa |
| T-419 Situacao no TSE com cor (F-25 / ADR-043) | OK | 03/09/2026: "em prazo recursal" ficou AMBAR e nao vermelho — pintar de vermelho afirmaria um desfecho que a fonte nao declara, sobre uma pessoa real. Renuncia e' cinza: e' ato do proprio candidato, nao decisao contra ele. O rotulo continua escrito porque cor sozinha nao informa quem tem daltonismo |
| T-418 Patrimonio detalhado, mandatos e exercicio (F-24 / ADR-042) | OK | 03/09/2026: dois marts novos (`fct_bem_candidatura`, `fct_patrimonio_declarado`). A descricao do bem NAO entra no mart: traz endereco residencial em 6,8% das linhas de 2026, e a protecao estrutural e' o campo nao existir. A serie nao calcula variacao — valor de aquisicao, nominal, autodeclarado. Achou a L-27: o arquivo de 2006 zera 34,8% das declaracoes, e sem o filtro a ficha desenharia uma queda a pico que nunca houve |
| T-417 Buscador na home (F-23 / ADR-041) | OK | 03/09/2026: com 20.162 fichas, chegar a uma exigia saber cargo E estado. Indice por prefixo de duas letras, 409 arquivos, o maior com 136 kB comprimido. A home carrega a lista de prefixos que existem para poder distinguir "nao ha' ninguem assim" de "o arquivo nao carregou" — 404 virando "nada encontrado" seria ausencia virando afirmacao (Regra 5). Indexar so' o nome de urna perdia 9 em cada 10: SILVA aparece em 301 nomes de urna e 3.322 completos, e `jose da silva` devolvia ZERO antes da correcao |
| T-415 Ficha propria para toda candidatura (F-18 / ADR-040) | OK | 03/09/2026: as 19.418 candidaturas proporcionais tinham listagem e mais nada — 1.126 nomes so' em SP, nenhum com endereco para abrir ou compartilhar. Mesmo caminho de codigo das majoritarias: duas rotinas de carga divergiriam, e a divergencia apareceria como ficha de deputado com menos rigor. Sem indicador socioeconomico atribuido a mandato de deputado (SPEC 2.2) |
| T-414 Envio incremental na publicacao (ADR-039) | OK | 03/09/2026: o manifesto passa a guardar hash e sobe POR ULTIMO. Subindo antes — como subia, por ser o primeiro na ordem alfabetica — uma publicacao interrompida deixaria no servidor um manifesto afirmando o hash de arquivos que nunca chegaram, e a proxima pularia justamente esses |
| T-413 Data por ficha, vinda do snapshot (ADR-038) | OK | 03/09/2026: o rodape mostrava quando o SITE rodou, e como `dim_candidato` tem um unico `_extracted_at` reescrito a cada ingestao, 100% das paginas mudavam por dia — quando so' ~5% das candidaturas mudam. Agora a ficha diz quando AQUELE dado mudou (`dbt_valid_from` do snapshot). Destrava o envio incremental, pre-requisito da F-18 |
| T-412 Limpeza de paginas orfas na publicacao (ADR-037) | OK | 03/09/2026: o gerador nao limpa a saida, e SEIS fichas com nome de urna antigo estavam vivas no ar — uma delas mostrando um nome que o TSE nao registra mais. Manifesto no servidor passa a identificar o que saiu, com teto de 25%, piso de 20 e recusa de inventario parcial. Pre-requisito da F-18 |
| T-411 Conferencia do trio SICONFI (Regra 6, ADR-035) | OK | 03/09/2026: a conferencia achou ERRO. A receita nao descontava as transferencias constitucionais (R$ 23,8 bi em MG 2023, virando superavit de R$ 24 bi num estado em Regime de Recuperacao Fiscal) e a declaracao das deducoes muda entre estados e anos. Receita trocada para a Receita Corrente Liquida (RREO Anexo 3), conferida ao centavo em 4 pontos. Resultado orcamentario retirado (L-26) |
| T-409 Atividade legislativa do Senado (F-22, ADR-034) | OK | 02/09/2026: fecha a L-20. 80 senadores, 28.600 proposicoes como AUTOR PRINCIPAL, em 42 fichas de 2026. `ordem = 1` validado em 48 comparacoes contra a flag oficial do endpoint descontinuado; classes mapeadas pela lista oficial de siglas. Relatoria vem vazia por limite da fonte, e a tela diz isso (L-25) |
| T-408 Pagina de quem financia as campanhas (ADR-033) | OK | 01/09/2026: `/doadores/` com 23.532 repasses, uma linha por financiador x candidatura, sem CPF. Publicar todas as pessoas fisicas foi decisao explicita do usuario, com o numero de exposicao (704 hoje -> 14.958) na mao. JSON de 2,8 MB que o servidor entrega em 443 KB por Brotli; a pagina desenha 200 linhas por vez |
| T-407 Ficha propria para os vices (ADR-032) | OK | 01/09/2026: 216 candidaturas (13 a vice-presidente, 203 a vice-governador) ganharam ficha, listagem, navegacao e sitemap. Vinculo com o titular nos dois sentidos. O site foi de 739 para 956 paginas. Suplente de senador (665) fica de fora — decisao separada |
| T-406 Ausencia de indicador dita na ficha (ADR-031) | OK | 01/09/2026: cada bloco de mandato passa a listar no rodape o que NAO esta' la' e por que, derivado do alcance real de cada serie (`fct_mandato_indicador_ausente`). Nasceu da pergunta "por que o Lula nao tem desemprego nos dois primeiros mandatos?" — a PNAD Continua comeca em 2012 (L-06), e a tela nao dizia. A metodologia afirmava que a ficha dizia; agora diz de verdade |
| T-405 Validacao dos indicadores contra fonte oficial (Regra 6) | OK | 01/09/2026: **14 de 18 conferem** com a publicacao oficial, varios exatos ate' o ultimo digito. A DESOCUPACAO foi trocada para a serie anual do IBGE por causa da conferencia (ADR-030) e passou a conferir. RENDIMENTO_MEDIO fica no "efetivamente recebido", agora nomeado na tela. O trio SICONFI segue sem publicacao externa para comparar. A pagina de metodologia tem a secao **Conferencia com a fonte oficial**. Ver [VALIDACAO.md](VALIDACAO.md) |
| T-410 Rename para Dossie Eleitoral (ADR-026) | OK | Repo `girocoju/dossie-eleitoral`, pasta local, site em `datadubaintel.com/dossie-eleitoral`, bucket `dossie-eleitoral-fotos`, variaveis `DOSSIE_*` (o prefixo `RADAR_` ainda resolve, com aviso). Publicado e conferido em 31/08/2026. O WIF amarra o repo em DOIS lugares (condicao do provider **e** binding da service account) — os dois aceitam os dois nomes; remover o antigo e' limpeza opcional. Ver ADR-011 |
| T-404 Publicacao do site | ✅ | "Publish to web" era recurso do Power BI e morreu com a ADR-018. A publicacao real: FTPS para a Hostinger, 1016 arquivos, com retomada por reconexao (ADR-027). O post de divulgacao nao e tarefa de engenharia e sai daqui |

## Fase 5 — Pos-eleicao

F-11 (financiamento): ✅ entregue em 28/08/2026 — saiu da fase 2 porque a
prestacao ja' esta' substantiva (R$ 3,59 bi sobre 7.722 candidaturas), mesmo sem
estar completa. F-12 (resultados 2026): ⬜ fase 2, apos 25/10/2026.

---

## Materializado no BigQuery em 27/08/2026

`dbt build`: **123 de 123** (3 seeds, 8 modelos de tabela, 5 views, 107 testes),
`Completed successfully`.

| Tabela | Linhas |
|---|---:|
| `raw_tse.candidatos` | 180.718 |
| `raw_tse.bens` | 509.136 |
| `stg.stg_tse__candidaturas` | 180.718 |
| `stg.stg_indicadores` | 2.856 |
| `marts.dim_candidato` | 180.346 |
| `marts.dim_partido` | 250 |
| `marts.fct_candidatura` | 180.346 |
| `marts.fct_indicador_uf_ano` | 3.360 |
| `marts.fct_mandato` | 11.777 |
| `marts.fct_mandato_indicador` | 818 |

`dbt build`: **129 de 129**, `Completed successfully`. Oito eleicoes gerais
(1998–2026) e o modulo "Durante o mandato" com 197 mandatos de Presidente e
Governador cruzados com 5 indicadores.

`fct_indicador_uf_ano` tem **0 linhas sem comparador nacional** — a regra da
Constituicao secao 2 esta' satisfeita no dado, nao so' no visual.

## Snapshot diario da situacao das candidaturas — a peca com prazo

`marts.snap_candidatura_2026` (SCD2) + `marts.fct_mudanca_candidatura` (eventos).
Primeira captura em **27/08/2026**: 20.765 candidaturas, 64,3% ainda aguardando
julgamento.

E' a unica tabela do projeto que **nao pode ser reconstruida das fontes**: o TSE
republica o estado atual e descarta o anterior. Cada dia sem rodar e' um dia de
historico perdido para sempre, ate' 04/10/2026.

O pipeline diario ja' esta' no ar e a serie **ja' esta' acumulando**. Primeira
mudanca capturada na segunda execucao, uma hora depois da primeira: tres
correcoes de nome de urna (MA, MT, RJ) que teriam sumido sem rastro.

## Propostas e entregas recentes

| # | O que | Estado |
|---|---|---|
| F-13 / [ADR-012](adr/ADR-012-fotos-de-candidatos.md) | Foto oficial dos candidatos de 2026 em bucket publico | ✅ **Entregue** — 20.765 fotos, 99,98% de cobertura |
| F-14 / [ADR-013](adr/ADR-013-proposta-de-governo.md) | Proposta de governo dos majoritarios | ✅ **Entregue** — 206 apresentaram, 5 nao constam, 20.558 nao se aplica |
| F-15 / [ADR-014](adr/ADR-014-ponte-legislativo.md) | Ponte de identidade com Camara e Senado | ✅ **Entregue** — 513 deputados por CPF, 81 senadores por nome+nascimento |
| F-16 / [ADR-015](adr/ADR-015-atividade-legislativa.md) | Atividade legislativa dos deputados | ✅ **Entregue** — 296.962 proposicoes de 710 deputados, so' `proponente = 1` |
| F-11 / [ADR-020](adr/ADR-020-financiamento-de-campanha.md) | Financiamento de campanha | ✅ **Entregue** — 43.610 receitas e 54.019 despesas sobre 7.722 candidaturas; CPF de doador hasheado na ingestao. Conferido ao centavo contra o TSE |
| F-20 / [ADR-025](adr/ADR-025-plenario-e-chapas.md) | Votos e presenca em plenario | ✅ **Entregue** — 2003-2026, 1,9 mi de votacoes e 2,5 mi de presencas, agregados por deputado/ano. Sem taxa de presenca |
| F-21 / [ADR-025](adr/ADR-025-plenario-e-chapas.md) | Chapa: vice e suplentes | ✅ **Entregue** — 889 vinculos, 887 resolvidos. O vinculo so' existe no DivulgaCandContas |
| F-27 / [ADR-046](adr/ADR-046-emendas-parlamentares.md) | Emendas parlamentares | ✅ **Entregue** — 788 fichas, uma linha por ano e nenhum total. 17% do arquivo o Portal publica sem autor, e a tela diz isso. Conferido contra o CSV somado fora do BigQuery (exato) e contra a cota da LDO |
| F-26 / [ADR-044](adr/ADR-044-comissoes-da-camara.md) | Comissoes na Camara | ✅ **Entregue** — onde cada deputado sentou, com que papel e por quanto tempo. Um colegiado por linha, com os periodos somados. Filiacao partidaria e comissao de MPV ficam fora de proposito |
| F-25 / [ADR-043](adr/ADR-043-situacao-com-cor.md) | A situacao no TSE ganha cor | ✅ **Entregue** — nove valores em quatro estados: deferido verde, pendente ambar, negado vermelho, renuncia cinza. Mesmo mapa na ficha e na listagem, serializado do Python para o JavaScript |
| F-24 / [ADR-042](adr/ADR-042-o-que-o-patrimonio-e.md) | De que o patrimonio e' feito, e o que a pessoa exerceu | ✅ **Entregue** — composicao dos bens por tipo oficial (12.732), declaracoes lado a lado desde 2006 (4.277), mandatos exercidos (2.006) e aviso de exercicio (501). Conferido contra o DivulgaCandContas: 12 de 12 ao centavo |
| F-23 / [ADR-041](adr/ADR-041-buscador-por-prefixo.md) | Buscar uma candidatura pelo nome | ✅ **Entregue** — busca na home sobre as 20.162 fichas, por nome de urna, nome completo ou numero na urna. Indice em 409 arquivos por prefixo; o navegador baixa um |
| F-18 / [ADR-040](adr/ADR-040-ficha-para-toda-candidatura.md) | Ficha propria para toda candidatura | ✅ **Entregue** — 19.418 fichas proporcionais + 529 majoritarias, 20.400 paginas. Exigiu envio incremental (ADR-039), CSS fora da pagina e sitemap dividido por cargo e UF |
| Indicadores IPCA e SELIC | Inflacao e juros para a pagina de presidenciaveis | ✅ **Entregue** — IPCA 1980-2025 (46 anos), Selic 1974-2025 (52 anos), so' `BR` |

## Correcao commitada, testada e NAO publicada

Sintoma: o bug foi corrigido, os testes passam, o commit esta' no `main` — e o
site continua mostrando o erro. Foi o que aconteceu em 29/08/2026: a ficha de
Lula seguiu oito horas dizendo "2006 · Presidente · Nao eleito" depois de a
correcao existir, e quem viu foi o usuario, de novo.

**A causa nao estava no codigo, estava na fila.** `cancel-in-progress: true`
valia para os dois jobs, entao cada gatilho novo matava o anterior:

    15:47  e8ba320  push      cancelado   <- a correcao do Lula e do Guto
    15:58  3858b01  push      cancelado   <- a pagina de metodologia
    16:14  7740c8e  push      cancelado   <- o glossario dos indicadores
    16:29  8709729  push      cancelado   <- pelo cron das 14h, atrasado ate' 17:27
    17:27  8709729  schedule  SUCESSO

Quatro pushes em 40 minutos mais um cron atrasado. O `pipeline` leva ~50 min,
entao a cadeia nunca chegava ao fim.

### O que mudou

`publicar` perdeu o `cancel-in-progress`. Para a CARGA cancelar e' correto — e'
idempotente e o dado mais novo vence. Para a PUBLICACAO e' o oposto: um deploy
cancelado nao deixa o site um pouco desatualizado, deixa exatamente como estava.

Ha' tambem `somente_publicar` no `workflow_dispatch`: republica o site a partir
do BigQuery atual, sem reingerir nada. E' o caminho de minutos para corrigir a
tela quando o dado ja' esta' certo.

### A parte que nenhuma configuracao resolve

Empilhar commits sem conferir se o anterior publicou. Depois de um push que
corrige algo VISIVEL, o certo e' esperar o run terminar e conferir em producao
antes do proximo.

## Job que falha em 1 segundo, sem runner e sem log

Sintoma: `runner_id: null`, `steps: []`, o job comeca e termina no mesmo segundo,
e `gh run view --log-failed` responde "log not found".

Parece cota de Actions estourada. **Nao era.** A causa em 28/08/2026 foi um grupo
de `concurrency` declarado com o MESMO nome nos dois niveis — no workflow e no
job. Grupos de concorrencia sao globais no repositorio: o run toma o grupo, e o
proprio job dele nunca consegue adquirir, entao morre antes de receber maquina.

O grupo fica no JOB, e so' la'. O nivel de workflow ficaria errado de qualquer
forma: cancelaria tambem o job `verificar`, que precisa rodar em todo PR.

Como distinguir de cota de verdade: cota aparece como erro de faturamento na aba
Actions e afeta TODOS os jobs; o conflito de grupo derruba so' o job que disputa o
grupo — aqui o `verificar` passava normalmente, em 56 segundos.

## Custo do pipeline: fontes anuais sao semanais

Independente do bug acima, a etapa socioeconomica nao deveria mesmo rodar todo
dia. O SICONFI faz 594 consultas com pausa de 1,5s em dois anexos — cerca de 30
minutos — e a DCA publica **uma vez por ano**. IDEB e' bienal, IDHM e' decenal.

Desde 28/08/2026 essas fontes rodam num cron **semanal**, aos domingos. O diario
ficou so' com o que muda de fato: TSE, fotos, propostas e legislativo — que e' o
que sustenta o snapshot de candidaturas, a unica serie irreproduzivel do projeto.

Estimativa: de ~35-50 min por dia para ~10 min, mais uma execucao semanal maior.

## Local e CI gravam nas MESMAS tabelas

Nao ha' ambiente de desenvolvimento separado: o projeto GCP e' um so'. Uma
carga local e uma execucao do Actions escrevem nas mesmas tabelas, e a ultima a
terminar vence.

Isso mordeu em 28/08/2026: um run de 48 minutos ainda em voo recarregou o SICONFI
com a versao que ainda coletava a Uniao pela DCA, e ressuscitou 22 linhas de
indicadores que ja' tinham sido removidos do catalogo. O `dbt build` local falhou
com orfaos que o codigo local nao produzia mais — e a causa nao estava em lugar
nenhum do repositorio.

O sinal que denuncia: `_extracted_at` das linhas orfas nao bate com o do NDJSON em
`data/staging`. Se divergir, alguem escreveu por cima.

Duas defesas desde entao:

1. `concurrency: cancel-in-progress` no workflow — uma execucao por vez.
2. Ao carregar local com um run em voo, cancele o run antes (`gh run cancel`).

## Identificadores de infraestrutura ficam fora da documentacao

O ID do projeto GCP, o e-mail da service account e o caminho do provider WIF NAO
aparecem neste repositorio. Nao sao credenciais — sao identificadores, e sozinhos
nao dao acesso a nada, porque a confianca esta' presa ao repositorio em duas
camadas (condicao do provider e permissao de personificacao). Mas tambem nao
servem para nada aqui, e superficie de ataque que nao existe nao precisa ser
defendida.

Onde eles vivem: `.env` (nao versionado) e variaveis do GitHub Actions.

## Permissoes da service account do pipeline (nao estao em codigo)

A service account do pipeline roda o CI por
Workload Identity Federation (ADR-011). O que ele precisa nao esta' versionado em
lugar nenhum — vive so' no IAM do GCP — entao fica registrado aqui:

| Recurso | Papel | Por que |
|---|---|---|
| projeto GCP | BigQuery Data Editor + Job User | criar dataset, carregar tabela, rodar dbt |
| bucket `dossie-eleitoral-fotos` | `roles/storage.objectViewer` | listar o que ja' subiu, para nao reenviar |
| bucket `dossie-eleitoral-fotos` | `roles/storage.objectCreator` | subir foto nova |

Concedido em 28/08/2026, depois de o CI falhar com **403 no upload de fotos**. A
etapa F-13 rodava local (credencial do dono) e quebrava no Actions.

Deliberadamente SEM `objectAdmin`: a ingestao lista e cria, nunca apaga. Se um dia
precisar remover foto de candidatura cancelada, o papel entra junto com o codigo
que apaga — nao antes.

## Uma armadilha do CI que ja' quebrou quatro execucoes

O `dbt build` pode passar na sua maquina e falhar no GitHub Actions **com o mesmo
codigo**. Aconteceu quatro vezes em 28/08/2026, sempre com a mesma cara:

```
FAIL 484 relationships_stg_indicadores_cod_indicador__cod_indicador__ref_dim_indicador_
```

**Por que:** o `dim_indicador.csv` e' gerado de `ingest/layouts/indicadores.yml`, e
o job `verificar` confere se os dois batem (`gerar_seeds.py --check`). Mas ninguem
confere o repositorio contra o BIGQUERY. Se voce ingere um indicador novo e nao
commita o par YAML + CSV, o BigQuery fica com dados de um indicador que o seed do
CI desconhece, e o teste de relacionamento acusa orfaos.

O guarda funciona — ele so' dispara no CI, nunca localmente, porque localmente o
seed nao commitado ja' esta' carregado.

**Regra pratica:** indicador novo = `indicadores.yml` + `dim_indicador.csv` no
MESMO commit da carga. Rodar `python scripts/gerar_seeds.py` antes de commitar.

## O caminho critico

1. `make ingest-historico` — os 8 layouts ja' estao conferidos. E' isto que faz
   `fct_mandato` e o modulo "Durante o mandato" deixarem de ser vazios.
2. Escrever o gerador do **Dossie Eleitoral**: script Python que le' `marts` e
   emite HTML + JSON estaticos, uma URL por candidato (ADR-018). O Power BI saiu:
   *Publish to web* nao tem layout mobile, URL por candidato nem indexacao.
3. Secrets do GitHub Actions (`RADAR_GCP_SA_JSON`, `RADAR_CPF_SALT`) para o
   pipeline agendado — o alvo `ci` usa service account, nao ADC.
