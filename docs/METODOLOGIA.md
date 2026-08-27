# Metodologia — Radar Brasil

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
- **IDHM** tem tres pontos em vinte anos. Nao descreve um mandato e por isso nao
  entra em `fct_mandato_indicador` como variacao — aparece so' como corte de
  contexto.
- **Mortalidade infantil por UF** ainda nao entrou: a unica serie do Ipeadata e'
  nacional. Ver [LACUNAS.md](LACUNAS.md).
- **Votos** (S4) ainda nao foram ingeridos; `votos_nominais` esta' sempre NULL.
- **Deputados e senadores** nao aparecem no modulo "Durante o mandato", por
  decisao explicita do escopo: o vinculo entre um parlamentar e um indicador
  estadual e' fraco demais para ser exibido sem induzir leitura errada.
- **Reais correntes.** Nenhum valor monetario e' deflacionado no MVP.

## 10. Reprodutibilidade

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
