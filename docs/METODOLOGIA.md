# Metodologia — Dossiê Eleitoral

> Este documento e' a versao longa do que aparece na pagina **Metodologia** do
> relatorio (F-09). Se algo aqui e a tela discordarem, a tela esta' errada.

---

## 1. O que este projeto afirma — e o que ele nao afirma

**Afirma:** quem sao os candidatos das eleicoes gerais de 2026, com o perfil que
eles proprios declararam ao TSE; e o que aconteceu com um conjunto de indicadores
socioeconomicos, por UF e no Brasil, ao longo do tempo.

**Nao afirma:** que um indicador subiu ou caiu **por causa** de um governo.

Essa distincao nao e' uma ressalva de rodape — e' a razao de o projeto existir do
jeito que existe. O modulo "Durante o mandato" responde *"o que aconteceu no
periodo"*, com o Brasil e a regiao ao lado, no mesmo grafico, sempre. Ele nao
responde *"o que o governante fez acontecer"*, porque nenhum dado publico
agregado por UF e ano permite responder isso.

Um governador nao controla o preco internacional da soja, a taxa Selic, a
pandemia, a migracao interestadual nem a politica salarial federal — e todos
esses fatores mexem nos indicadores da UF dele. Atribuir a variacao ao mandato
seria confundir o que aconteceu **durante** com o que aconteceu **por causa de**.

Por isso:

- nao existe ranking de politicos no produto;
- nao existe nota, score ou "melhor governo";
- `delta_vs_brasil` e' descrito como *diferenca entre duas variacoes observadas*,
  nunca como desempenho;
- a coluna `aviso_metodologico` viaja junto com cada linha de
  `fct_mandato_indicador`, para que o aviso nao se perca em nenhum caminho de
  exibicao.

## 2. Fontes e data de extracao

Todo dado e' publico. Cada linha carrega `_extracted_at`, `_source_url` e, no
caso do TSE, o `sha256` do pacote de onde veio.

| Fonte | O que traz | Cobertura conferida | Conferido em |
|---|---|---|---|
| TSE — `consulta_cand` | Candidaturas | 1998–2026 (2026 conferido) | 2026-08-27 |
| TSE — `bem_candidato` | Bens declarados | idem | 2026-08-27 |
| TSE — `consulta_vagas` | Vagas em disputa | idem | 2026-08-27 |
| TSE — `consulta_coligacao` | Coligacoes e federacoes | idem | 2026-08-27 |
| TSE — `consulta_cand_complementar` | Julgamento, reeleicao, despesa maxima | 2026 | 2026-08-27 |
| IBGE/SIDRA t/5938 | PIB a precos correntes | 2002–2023, 27 UFs + BR | 2026-08-27 |
| IBGE/SIDRA t/6579 | Populacao residente estimada | 2001–2025, 27 UFs + BR | 2026-08-27 |
| IBGE/SIDRA t/4099 | Taxa de desocupacao (PNAD Continua) | 2012–2025, 27 UFs + BR | 2026-08-27 |
| IPEA — Ipeadata `AVIOL12_THOMIC` | Taxa de homicidios | 1980–2024, 27 UFs + BR | 2026-08-27 |

O que ainda **nao** entrou esta' em [LACUNAS.md](LACUNAS.md), com o motivo.
Nenhum buraco de serie e' preenchido por interpolacao, media ou estimativa.

### Uma armadilha do pacote do TSE

O `.zip` de cada dataset traz um CSV por unidade eleitoral (`_AC`, `_SP`, ..., `_BR`)
**e** um `_BRASIL` que e' o consolidado de todos eles. Ler os dois duplica cada
registro — e a duplicata e' silenciosa, porque todos os totais continuam
plausiveis, so' que dobrados. O layout casa somente siglas de duas letras, e a
ingestao falha se o numero de unidades lidas nao for 28 (27 UFs + BR) ou se
alguma chave declarada se repetir.

## 3. Como o perfil do candidato e' lido

Perfil vem **do que o candidato declarou ao TSE**, e nao de uma classificacao
feita pelo projeto. Genero, cor/raca, grau de instrucao e ocupacao sao
autodeclarados; o projeto reproduz os rotulos da fonte sem reagrupar.

Duas coisas que a conferencia do pacote de 2026 revelou e que mudam a leitura:

1. **`DS_SITUACAO_CANDIDATURA` vem `#NE`** enquanto o registro esta' sub judice.
   Antes da eleicao, a informacao util e' `DS_SITUACAO_JULGAMENTO`
   (DEFERIDO / INDEFERIDO / ...), que so' existe no arquivo complementar.
2. **`ST_REELEICAO` vem `#NE` em 2026.** Por isso `is_reeleicao` e' **derivada**:
   e' reeleicao quando a pessoa esta' exercendo, no ano da eleicao, mandato do
   mesmo cargo na mesma unidade eleitoral. O valor bruto da fonte fica guardado
   em `reeleicao_declarada`, para quem quiser auditar a diferenca.

**Bens declarados** sao valores nominais em reais correntes do ano da eleicao,
sem deflacionamento. Comparar o patrimonio declarado em 2014 com o de 2026 sem
corrigir pela inflacao nao faz sentido, e o produto nao faz essa comparacao.
Dentro de um mesmo ano, a distribuicao e' lida por mediana e quartis — a media
de bens declarados e' dominada por poucos casos extremos.

## 4. Identidade da pessoa entre eleicoes

`SQ_CANDIDATO` muda a cada pleito. A chave de pessoa (`id_pessoa`) e':

1. `cpf_hash` = HMAC-SHA256 do CPF com salt secreto — ver
   [ADR-005](adr/ADR-005-chave-de-pessoa.md), [ADR-006](adr/ADR-006-hmac-no-cpf.md);
2. na ausencia de CPF, hash de `nome_completo` normalizado + `data_nascimento`,
   com `link_confiavel = false`;
3. sem nenhum dos dois, `id_pessoa` fica NULL e a candidatura **nao** gera mandato.

O caso 2 e' falivel: homonimos nascidos no mesmo dia existem. Toda trajetoria que
depende dele e' sinalizada na tela. A taxa de vinculacao por ano e' medida pela
analise `relatorio_vinculacao_pessoa`, nao estimada.

**O CPF em claro nunca e' gravado** — nem em arquivo local, nem no BigQuery.
Titulo de eleitor e e-mail sao descartados na leitura do CSV
([ADR-007](adr/ADR-007-hash-na-ingestao.md)).

## 5. Janela de mandato

Grao anual. A posse ocorre em 1o de janeiro (executivo) do ano seguinte a'
eleicao, entao:

| Cargo | Janela |
|---|---|
| Presidente, Governador | `ano_eleicao + 1` a `ano_eleicao + 4` |
| Senador | `ano_eleicao + 1` a `ano_eleicao + 8` |
| Deputados | `ano_eleicao + 1` a `ano_eleicao + 4` |

`motivo_fim` so' e' preenchido quando a fonte informa cassacao. Fora disso fica
`nao informado` — **nao** `fim regular` —, porque renuncia, morte no exercicio e
afastamento nao estao no `consulta_cand`, e rotular como "regular" o que nao se
sabe seria afirmar mais do que o dado permite.

## 6. Como as pontas da janela sao escolhidas

Esta e' a decisao metodologica mais consequente do projeto.

- **Ponta inicial** (`ano_referencia_inicio`): o ano **anterior** a' posse. E' a
  situacao herdada, e nao o primeiro ano ja' sob o novo governo. Quando esse ano
  nao existe na serie, usa-se o primeiro ano disponivel dentro da janela e
  `base_e_heranca` fica `false`.
- **Ponta final** (`ano_referencia_fim`): o ultimo ano da serie que ainda esteja
  dentro da janela.

**Defasagem.** O PIB estadual sai com cerca de dois anos de atraso: em agosto de
2026 a serie do IBGE terminava em 2023. Quando a ponta final e' anterior ao fim
do mandato, `janela_incompleta = true` e a tela avisa. O projeto **nao**
extrapola o ano que falta.

## 7. Comparadores

Toda linha de `fct_indicador_uf_ano` carrega, alem do valor da UF:

- `valor_brasil` — o mesmo indicador e ano no agregado nacional publicado pela
  fonte (nao uma media das UFs);
- `valor_regiao` — **media simples** entre as UFs da regiao. E' um comparador de
  contexto, nao um agregado ponderado por populacao ou PIB, e esta' rotulado como
  tal onde aparece.

Os comparadores vivem na mesma linha do fato de proposito: assim nao existe
caminho no relatorio que mostre o numero de uma UF sem ter o comparador
disponivel. Um teste (`assert_indicador_uf_tem_comparador`) falha o pipeline se
isso for quebrado.

## 8. Indicadores derivados

`PIB_PER_CAPITA` nao existe por UF na tabela 5938 do SIDRA (conferido em
27/08/2026); e' calculado como `PIB (R$ mil) * 1000 / populacao`, no BigQuery, e
so' existe nos anos em que as duas series coexistem. Na pratica isso significa
que **ele para em 2021**: a tabela de estimativas de populacao nao publica anos de
Censo (2007, 2010, 2022, 2023), justamente os dois ultimos do PIB. Ver
[L-12](LACUNAS.md).

`DESOCUPACAO` e' trimestral na fonte. O valor anual e' a **media simples dos
quatro trimestres**, e um ano com menos de quatro trimestres e' descartado — em
agosto de 2026, por exemplo, o ano de 2026 tinha so' dois trimestres publicados e
ficou de fora. Meio ano de dado nao vira "o ano".

`direcao_desejavel` (cima / baixo / neutro) existe **apenas** para escolher a cor
neutra de tendencia no relatorio. Nao e' juizo sobre gestao e nao alimenta
nenhum calculo.

## 9. Limites conhecidos

- **Serie curta para desemprego.** A PNAD Continua comeca em 2012; mandatos
  anteriores nao tem esse indicador.
- **IDHM para em 2010.** Tres pontos decenais (1991, 2000, 2010), por UF, vindos
  do Ipeadata. O mais recente e' anterior a TODOS os mandatos que o painel cobre,
  entao ele nao descreve mandato nenhum — serve para dizer de onde o estado
  partiu. Nao produz variacao em `fct_mandato_indicador`, e isso nao depende de
  filtro: a janela de mandato tem no maximo seis anos e os pontos distam dez, logo
  nenhuma janela contem dois. Conferido em 28/08/2026.
- **Mortalidade infantil** cobre 2000-2016 por UF (SIDRA t/3834). Mandatos
  posteriores a 2016 nao tem esse indicador.
- **Deputados e senadores** nao aparecem no modulo "Durante o mandato", por
  decisao explicita do escopo: o vinculo entre um parlamentar e um indicador
  estadual e' fraco demais para ser exibido sem induzir leitura errada. O que eles
  tem e' atividade legislativa (seccao 12), que e' ato proprio.
- **Reais correntes**, com UMA excecao. Nenhum valor monetario e' deflacionado,
  exceto `RENDIMENTO_MEDIO`, que ja' vem real da PNAD Continua. Nao desconte
  inflacao dele de novo, e nao o compare diretamente com PIB ou receita, que sao
  nominais.
- **Serie de indicadores comeca em 1980.** `stg_indicadores` corta ai'. A Selic
  existe desde 1974 no Ipeadata, mas os seis primeiros anos ficam de fora para nao
  criar um periodo em que so' um indicador tem dado.

## 10. Orcamento: o federal e o estadual vem de fontes diferentes

Nao e' inconsistencia, e' correcao. Ate' 28/08/2026 os dois vinham da DCA do
SICONFI, e o federal estava errado.

| Nivel | Fonte | Indicadores |
|---|---|---|
| Estados | SICONFI/RREO (receita) e DCA (despesa) | `RECEITA_ESTADUAL` (Receita Corrente Líquida, LRF), `DESPESA_ESTADUAL` (empenhada) |
| Uniao | Tesouro/RTN | `RECEITA_LIQUIDA_UNIAO`, `DESPESA_PRIMARIA_UNIAO`, `RESULTADO_PRIMARIO_UNIAO` |

**Por que.** A receita da DCA inclui operacoes de credito — divida emitida para
cobrir o deficit, contada como receita. Na Uniao de 2020 isso foi R$ 1.647,9 bi,
45% do total, e receita menos despesa tendia a zero por identidade contabil: a
serie dava -48 bi para um ano cujo resultado primario foi -743 bi. Para 2025
chegava a mostrar "superavit de R$ 635 bi" onde havia deficit de 61,7 bi.

Nos estados a mesma distorcao e' de 0,1% a 1,1% da receita, e a conta vale. Ver
[ADR-017](adr/ADR-017-orcamento-federal-pelo-rtn.md) e L-22.

**O que a serie federal NAO e':** nao e' o resultado do setor publico consolidado
(que inclui estados, municipios e estatais) nem o resultado nominal (que inclui
juros da divida, R$ 892 bi so' em 2025). E' o Governo Central, primario — o nivel
e o conceito pelos quais um presidente responde.

**Comparabilidade:** o resultado federal e o estadual NAO se somam nem se
comparam. Sao conceitos diferentes, de entes diferentes, com metodologias
diferentes. A tela os mostra em paginas diferentes.

## 11. Inflacao e juros: leitura com cuidado extra

`IPCA` e `SELIC` existem so' no nivel `BR` — nao ha' versao por UF, e isso e'
intencional, nao lacuna. Sao series da pagina de presidenciaveis.

**IPCA.** A fonte e' mensal e acumulada no ano, entao o valor anual e' o de
**dezembro**, nunca a media dos meses: a media de valores acumulados nao significa
nada (janeiro acumula um mes, dezembro acumula doze) e daria cerca de metade da
inflacao real. Ano incompleto nao entra — em agosto de 2026 o acumulado ate' julho
existe, mas nao e' "a inflacao de 2026".

**Selic.** A taxa e' definida pelo COPOM, e desde a **LC 179/2021** o Banco Central
tem autonomia formal, com mandatos de presidente e diretores **descasados** do
mandato presidencial. Atribuir juros a quem estava na Presidencia e' menos
defensavel do que qualquer outro indicador do projeto — inclusive menos do que o
PIB. Entra como contexto do periodo, e a tela diz isso.

Por isso `direcao_desejavel` da Selic e' `neutro`: juro alto nao e' "ruim" nem juro
baixo "bom" — depende inteiramente da inflacao do momento. Colorir tendencia ali
seria editorializar.

## 12. Atividade legislativa: por que nao ha' um numero so'

`fct_atividade_legislativa` **nao tem** linha "total de proposicoes do deputado".
O grao inclui `classe_proposicao`, de proposito.

O numero unico que circula na imprensa e' enganoso por tres motivos, todos medidos
nesta base em 2025:

| Problema | Medicao |
|---|---|
| Assinatura contada como autoria | 21,4% das linhas de autoria sao apoio; o maior requerimento do ano tem 264 assinaturas |
| Tipos somados como iguais | 7.695 projetos de lei · 31.479 requerimentos de retirada de pauta · 15.501 pareceres de relator |
| Destino ausente | 53% das proposicoes vem com situacao em branco na fonte |

As cinco classes: `normativa` (propos norma), `fiscalizacao` (pediu contas ao
Executivo), `relatoria` (analisou o texto de outro — **nao e' autoria**),
`procedimental` (rito, homenagem, emenda) e `outra` (residuo, 5,8%).

**Nao existe taxa de aprovacao** neste projeto. Aprovar depende de estar na base do
governo, nao do merito do texto: a taxa puniria a oposicao por ser oposicao, em
qualquer governo, e viraria placar. Ha' `qt_virou_norma` em numero absoluto ao lado
do total.

**`qt_destino_desconhecido` e' separado de `qt_em_tramitacao`.** Ausencia de
informacao nao e' andamento.

## 13. Reprodutibilidade

```bash
make bootstrap
make ingest ANO=2026
make ingest-socio
make dbt-build
```

Nenhum CSV e' editado a mao. O download e' idempotente e verificado por sha256;
recarregar um ano substitui a particao daquele ano e nada mais. Se o resultado da
sua execucao divergir do publicado, a diferenca esta' em `_extracted_at`: as
fontes sao republicadas.
