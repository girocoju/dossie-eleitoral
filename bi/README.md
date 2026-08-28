# `bi/` — ARQUIVADO

> **Este diretorio nao esta' mais em uso.** Ver
> [ADR-018](../docs/adr/ADR-018-site-estatico-em-vez-de-bi.md).

O produto publico do projeto — o **Dossie Eleitoral** — passou a ser um site
estatico gerado a partir dos marts, e nao um relatorio de BI publicado em iframe.

**Por que parou:** o *Publish to web* do Power BI nao suporta layout mobile, nao
da' URL por candidato e nao e' indexavel pelo Google. Sao justamente os tres
canais pelos quais um produto publico circula. O Looker Studio tem os mesmos
limites. A escolha nunca foi entre as duas ferramentas de BI — era entre publicar
dentro de um iframe ou publicar na web.

**Por que continua aqui:** o modelo semantico em TMDL
(`RadarBrasil.SemanticModel/definition/model.tmdl`) e' um registro legivel do
modelo estrela — relacionamentos, hierarquias e medidas descritos em texto. Serve
de documentacao do desenho dimensional, independente da ferramenta.

Apagar seria perda sem ganho; deixar sem aviso sugeriria que esta' vivo.

---

_Conteudo original abaixo, preservado como estava._

# Power BI — `RadarBrasil.pbip`

Formato PBIP: **texto, versionavel** ([ADR-001](../docs/adr/ADR-001-power-bi.md)).
O modelo semantico esta' em TMDL; o relatorio, em JSON.

## O que ja' esta' escrito aqui

- **Modelo semantico completo** (`RadarBrasil.SemanticModel/`): 10 tabelas com
  colunas tipadas, descricoes, 11 relacionamentos e 20 medidas DAX — incluindo as
  medidas de rodape (`Extraido em`, `Fontes`) e `Aviso metodologico`.
- **Conexao parametrizada**: `ProjetoGCP` e `DatasetMarts` sao parametros do
  Power Query. Trocar o projeto GCP nao exige mexer em nenhuma consulta.
- **Import mode** em todas as particoes ([ADR-002](../docs/adr/ADR-002-import-mode.md)).
- **Tema neutro** (`RadarBrasilNeutro.json`): paleta dessaturada, sem cor de
  partido e sem verde/vermelho de aprovacao (Constituicao secao 1).
- **As 9 paginas do hub**, criadas e ordenadas: Visao Geral → Presidencia →
  Governadores → Senado → Camara → Assembleias → Contexto Socioeconomico →
  Durante o Mandato → Metodologia.

## O que falta — e por que

**Os visuais dentro de cada pagina.** As paginas existem, vazias.

Isso e' deliberado: layout de visual em Power BI e' um JSON de posicionamento que
so' faz sentido montado na ferramenta, e escrever isso a mao produz um arquivo
fragil que abre quebrado. O modelo — que e' a parte que exige decisao de
engenharia e onde mora o risco de erro — esta' pronto e revisavel em texto.

## Como abrir

1. Materialize os marts: `make dbt-build` (exige credenciais GCP — ver
   [STATUS](../docs/STATUS.md), T-002).
2. Abra `RadarBrasil.pbip` no **Power BI Desktop** (Windows).
   Em *Opcoes → Recursos de visualizacao*, o formato PBIP com **TMDL** e
   **PBIR** precisa estar habilitado.
3. Ao carregar, informe os parametros `ProjetoGCP` (ex.: `radar-brasil`) e
   `DatasetMarts` (ex.: `marts`).
4. Autentique no conector do BigQuery com a conta que tem acesso ao projeto.

## Regras de tela que nao sao negociaveis

Ao montar os visuais, estas regras vem da Constituicao (SPEC secao 0) e valem
como criterio de revisao de cada pagina:

1. **Nenhum numero de UF sem comparador.** Todo grafico de indicador mostra a
   linha do Brasil junto. O dado ja' vem assim de `fct_indicador_uf_ano`; o
   visual so' precisa nao esconder.
2. **A pagina "Durante o Mandato" exibe o texto fixo** *"Indicadores refletem o
   periodo; nao medem o efeito do mandato."* — use a medida `Aviso metodologico`,
   que ainda acrescenta o aviso de serie incompleta quando for o caso.
3. **Nada de ranking de politico.** Sem "top 10 melhores governos", sem semaforo,
   sem seta verde/vermelha em `delta_vs_brasil`. A variacao e' descritiva.
4. **Rodape em toda pagina** com fonte e data de extracao: medidas `Fontes` e
   `Extraido em`.
5. **Cor de partido so' sob toggle explicito** do usuario. O tema padrao e' neutro.
6. **Sinalize a janela incompleta**: quando `janela_incompleta = true`, o periodo
   exibido termina antes do fim do mandato.
7. Antes de dar uma pagina por pronta, pergunte: *"alguem pode ler isto como
   endosso ou ataque a um candidato?"* Se sim, refaca (SPEC secao 12, risco 3).

## Regenerar o esqueleto

```bash
python scripts/gerar_modelo_bi.py
```

**Cuidado:** isso sobrescreve o TMDL. Depois que voce salvar pelo Power BI
Desktop, o Desktop e' o dono do arquivo. Use `--check` no CI apenas para saber se
o modelo divergiu; divergencia depois de edicao manual e' esperada.
