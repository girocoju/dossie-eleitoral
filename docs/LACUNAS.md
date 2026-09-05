# Lacunas conhecidas

> SPEC secao 9: "Ao encontrar dado ausente em uma UF/ano: registrar aqui, **nao preencher**."
>
> Nenhum item desta lista e' contornado por interpolacao, media ou estimativa.
> Enquanto estiver aqui, o dado simplesmente nao existe no produto — e a tela diz isso.

Ultima revisao: **2026-09-04**

---

## L-01 · Layout do TSE conferido so' para 2026

**O que falta:** `ingest/layouts/tse_{ano}.yml` esta' com `verificado: false` para
1998, 2002, 2006, 2010, 2014, 2018 e 2022. Os aliases foram declarados a partir do
padrao atual do portal de dados abertos, mas o header real desses anos ainda nao
foi lido nesta base de codigo.

**Impacto:** a carga do historico (F-02) pode falhar em campo obrigatorio ou
resolver menos campos do que o esperado. O loader falha ruidosamente — nao carrega
errado em silencio.

**Como fechar:** `make verify-layout ANO=2018` para cada ano; ajustar o YAML
conforme o `leiame.pdf`; marcar `verificado: true`.

---

## L-02 · Votos por candidato — FECHADA em 28/08/2026

142.086 linhas em `raw_tse.votacao`, sete eleicoes (1998–2022), agregadas na
ingestao a partir de ~2 GB e dezenas de milhoes de linhas de municipio x zona.

Validado contra a historia: FHC 35.936.382 no 1o turno de 1998; o vencedor de 2022
com 117.605.503 votos somando os dois turnos.

Tres achados que a ingestao expos:

1. **A coluna de votos troca de lugar entre anos.** Em 1998 `QT_VOTOS_NOMINAIS`
   vem ZERADO e o valor esta' em `_VALIDOS`; nos anos recentes e' o inverso. As
   duas sao somadas e a regra de escolha esta' explicita em `stg_tse__votacao`.
2. **`SG_UE` muda de significado.** Em 1998 e' a UF; em 2002 e 2010 e' o CODIGO DO
   MUNICIPIO. Agregar por ele fez 2002 saltar de 16 mil para 1,37 milhao de
   grupos. A agregacao usa `SG_UF`, consistente entre anos, e a unidade disputada
   e' derivada no dbt.
3. **O `_BRASIL` aqui e' o arquivo CERTO** — o oposto do `consulta_cand`. O DF nao
   tem arquivo proprio na votacao de 1998: existe so' dentro do BRASIL.

Restou aberta a quebra por municipio — ver L-19.

---

## L-03 · Mortalidade infantil — FECHADA PARCIALMENTE em 28/08/2026

**Resolvida pelo IBGE, nao pelo DATASUS.** O TabNet e' formulario HTML e o Atlas
do PNUD esta' inacessivel; mas a SIDRA t/3834 traz a taxa por UF, ja' reconciliada
e sem o vies de sub-registro que afeta a contagem bruta de obitos. 476 observacoes,
28 unidades. Custou uma linha no catalogo — nenhum codigo novo.

**O que continua aberto: a serie termina em 2016.** Mandatos posteriores nao tem
este indicador, e a ausencia aparece na tela em vez de ser preenchida.

**Por que nao usei a t/7362**, que iria de 2000 a 2060: e' tabela de PROJECAO. Os
anos futuros sao modelo e mesmo os passados sao saida de modelo demografico.
Misturar projecao com observacao numa serie historica seria exatamente o tipo de
coisa que este projeto recusa. Usa-la exigiria, alem disso, suporte a
classificacoes na ingestao do SIDRA — a serie vive numa classificacao `Ano`, e a
tabela tem DUAS dimensoes com esse nome, o que quebra a deteccao automatica de
periodo.

---

## L-04 · IDHM tem tres pontos decenais e para em 2010

**O que falta:** nada a obter nesta serie — e' a natureza da fonte. Ingerida em
28/08/2026 pelo Ipeadata (`ADH_IDHM`): **1991, 2000 e 2010**, por UF e Brasil.

A redacao anterior desta lacuna dizia "(2000, 2010, 2021)". Estava errada em duas
pontas: falta 1991, que existe, e **nao ha' 2021** — a atualizacao do Atlas com o
Censo 2022 nao esta' nesta serie do Ipeadata.

**Impacto:** o ponto mais recente e' ANTERIOR a todos os mandatos que o painel
cobre. O IDHM nao entra em `fct_mandato_indicador` como variacao — e nao por
regra escrita, mas por aritmetica: a janela de mandato vai de `ano_inicio - 1` a
`ano_fim`, no maximo seis anos, e os pontos distam dez. Nenhuma janela contem
dois. Ele aparece so' como linha de base historica.

**Como fechar:** so' com a serie do Censo 2022, quando o Ipeadata publica-la.
Enquanto isso e' limite da fonte, documentado em METODOLOGIA secao 9.

---

## L-05 · FECHADA — IDEB e IDHM ingeridos por caminhos diferentes

**Situacao:** **fechada** em 28/08/2026 (as duas pontas)

O diagnostico original desta lacuna estava errado. Dizia que os dois hosts
"resetam a conexao no handshake TLS". Eram duas causas distintas, e nenhuma delas
era reset:

| Host | Causa real | Desfecho |
|---|---|---|
| `www.atlasbrasil.org.br` | Certificado Let's Encrypt **vencido em 24/08/2026** | Contornado: a serie estava no Ipeadata |
| `download.inep.gov.br` | Certificado **valido**; faltava o **intermediario** na cadeia servida | Resolvido: intermediario versionado (ADR-016) |

### IDHM — 84 observacoes, 1991/2000/2010

A mesma serie do Atlas esta' no Ipeadata (`ADH_IDHM`), que o projeto ja' consumia.
Zero codigo novo. Valores conferidos contra o Atlas (Brasil 2010 = 0,727).
Limite que fica: para em 2010, antes de todos os mandatos do painel — linha de
base historica, nunca indicador de mandato. Ver L-04.

### IDEB — 308 observacoes, 11 edicoes de 2005 a 2025

Rede publica, anos finais do ensino fundamental, 27 UFs mais Brasil. E' a serie
com MELHOR encaixe em janela de mandato de todo o projeto.

Tres obstaculos, todos resolvidos e documentados na ADR-016:

1. **Cadeia TLS incompleta.** O servidor nao envia o intermediario da RNP ICPEdu.
   Versionado em `certs/`, injetado so' para esse host.
2. **URLs invisiveis.** A pagina nao tem link nenhum no HTML; os arquivos vem de
   um endpoint declarado em `data-url`. `python -m ingest.ideb verify` refaz a
   descoberta e falha se o INEP renomear.
3. **Defeito na planilha da fonte.** No arquivo do Brasil, a coluna do IDEB 2023
   veio sem o codigo de maquina. Sem remendo, o Brasil perderia 2023 e 27 estados
   ficariam sem comparador naquele ano.

**O que continua fora:** as abas de anos iniciais e ENSINO MEDIO estao no mesmo
arquivo e sao lidas pelo mesmo codigo — falta so' uma entrada de catalogo. O
ensino medio interessa especialmente, por ser majoritariamente estadual e portanto
o mais proximo da responsabilidade de um governador. Pergunta aberta no SPEC 11.

**O que nunca entra:** as METAS do IDEB. "Atingiu a meta" e' avaliacao, nao
descricao (Constituicao 0.1). O parser le' `VL_OBSERVADO` e ignora `VL_PROJECAO`.

---

## L-06 · Desemprego so' a partir de 2012

**O que falta:** nada a obter. A PNAD Continua comeca em 2012T1.

**Impacto:** mandatos iniciados antes de 2012 (eleicoes de 1998, 2002, 2006) nao
tem esse indicador em `fct_mandato_indicador`. O par mandato x indicador
simplesmente nao existe — nao aparece zerado.

**Desde 01/09/2026 a ficha DIZ isso** (ADR-031). Antes ela apenas omitia a linha,
e a pergunta "por que o Lula nao tem desemprego nos dois primeiros mandatos?" nao
tinha resposta na tela. Agora o rodape do bloco daquele mandato traz "Sem dado
para esta janela: Desemprego e Rendimento do trabalho (a serie comeca em 2012)".
A lacuna continua exatamente a mesma; o que mudou e' que ela deixou de ser
silenciosa.

**Como fechar:** nao fecha sem trocar de fonte (a PNAD antiga tem metodologia
diferente e nao e' comparavel; emendar as duas series criaria uma quebra que
seria lida como fato).

---

## L-07 · PIB estadual com dois anos de defasagem

**O que falta:** 2024 e 2025. Em 27/08/2026 a serie do IBGE terminava em 2023.

**Impacto:** todo mandato que termina em 2026 fica com `janela_incompleta = true`
para PIB e PIB per capita. A tela sinaliza.

**Como fechar:** sozinho, quando o IBGE publicar. A ingestao e' idempotente e
incorpora os anos novos na proxima execucao.

---

## L-08 · Situacao da candidatura de 2026 ainda sub judice

**O que falta:** nada — e' o calendario eleitoral.

**Impacto:** `DS_SITUACAO_CANDIDATURA` vem `#NE` (codigo `-3`) enquanto o registro
esta' em julgamento. A informacao util antes da eleicao e' `situacao_julgamento`
(DEFERIDO / INDEFERIDO / ...), que vem do arquivo complementar.

**Como fechar:** sozinho, conforme o TSE julga os registros. A ingestao roda
diariamente ate' 04/10/2026.

---

## L-09 · `ST_REELEICAO` vazio em 2026

**O que falta:** nada — a fonte so' preenche apos a eleicao.

**Impacto:** `is_reeleicao` e' derivada do historico de mandatos e depende,
portanto, da qualidade da vinculacao de pessoa (L-10). O valor bruto da fonte
fica em `reeleicao_declarada`.

---

## L-10 · FECHADA em 02/09/2026 — vinculacao de pessoa medida por ano

**Situacao:** FECHADA. A analise `relatorio_vinculacao_pessoa` foi rodada contra o
historico carregado. Percentuais MEDIDOS, nao estimados:

| ano | candidaturas | por CPF | fallback nome+nascimento | sem chave |
|---|---|---|---|---|
| 1998 | 15.040 | 96,9% | 3,0% (445) | 0,1% (14) |
| 2002 | 18.049 | 98,1% | 0,6% (113) | 1,3% (233) |
| 2006 | 19.263 | **100%** | 0 | 0 |
| 2010 | 22.537 | **100%** | 0 | 0 |
| 2014 | 26.195 | 99,9% | 0,1% (24) | 0 |
| 2018 | 29.227 | 99,6% | 0 | 0,4% (108) |
| 2022 | 29.270 | 99,9% | 0 | 0,1% (29) |
| 2026 | 20.837 | **100%** | 0 | 0,01% (3) |

**O que isso quer dizer:** a trajetoria eleitoral e' quase inteiramente ligada por
CPF, que nao tem homonimia. O fallback por nome + data de nascimento — o unico que
poderia juntar duas pessoas diferentes — pesa em **1998 e 2002, e so'**: 558
candidaturas nos dois anos somados, de 33 mil. Onde ele foi usado, a tela sinaliza
`link_confiavel = false`.

**O que continua verdadeiro:** o ano com mais candidatura sem chave nenhuma e' 2002
(1,3%). Essas nao entram em `fct_mandato` e nao viram trajetoria — ausencia
declarada, nunca aproximada por nome.

---

## L-11 · `motivo_fim` quase sempre "nao informado"

**O que falta:** renuncia, morte no exercicio e afastamento nao estao no
`consulta_cand`.

**Impacto:** `motivo_fim` so' distingue `cassacao` de `nao informado`. O projeto
nao rotula como "fim regular" o que nao sabe.

**Como fechar:** exigiria outra fonte (diarios oficiais, Camara/Senado). Fora do
escopo do MVP.

---

## L-12 · Estimativas de populacao nao cobrem anos de Censo

**O que falta:** 2007, 2010, 2022 e 2023 na tabela 6579 do SIDRA (conferido em
27/08/2026). Sao anos de Censo/Contagem, publicados em outras tabelas.

**Impacto:** `PIB_PER_CAPITA` e' derivado de PIB / populacao e so' existe onde as
duas series coexistem — ou seja, **para em 2021**, apesar de o PIB ir ate' 2023.
Perdem-se justamente os dois anos mais recentes. O modelo nao inventa o
denominador: o par (UF, ano) simplesmente nao aparece.

**FECHADA PARCIALMENTE em 28/08/2026.** A tabela 4709 (Censo 2022) foi
acrescentada ao catalogo como `POPULACAO_CENSO`, indicador separado para nao
esconder a quebra metodologica entre estimativa e censo. O
`fct_indicador_uf_ano` usa a estimativa e recorre ao censo so' onde ela falta.

Resultado: **PIB per capita passou de 2002-2021 para 2002-2022**, o que completa a
janela de todos os governadores eleitos em 2018.

**O que continua aberto:** 2023 nao tem populacao publicada em nenhuma das duas
tabelas (nem estimativa, nem censo). Como o PIB vai ate' 2023, o PIB per capita
fica um ano atras dele. 2007 e 2010 seguem sem preenchimento — sao anteriores ao
inicio da serie de PIB, entao nao afetam nenhum indicador derivado.

---

## L-13 · Composicao da populacao nao ingerida

**O que falta:** distribuicao de genero e cor/raca da populacao brasileira por UF.

**Impacto:** o perfil dos candidatos (34,9% de mulheres, 48,7% pretos e pardos)
nao pode ser comparado com a populacao **dentro do produto** — e comparar com um
numero lembrado de fora violaria a Constituicao secao 3 (fonte e data de extracao em
toda visualizacao). Hoje a tela mostra a composicao das candidaturas sem base
populacional ao lado.

**Como fechar:** ingerir a PNAD Continua Caracteristicas Gerais (SIDRA) por UF,
ano, sexo e cor/raca, e acrescentar como comparador em `fct_indicador_uf_ano`.

---

## L-14 · Bens declarados nao existem antes de 2006

**O que falta:** `bem_candidato_1998.zip` e `bem_candidato_2002.zip`. O CDN do TSE
responde **404** para os dois (conferido em 27/08/2026, na mesma execucao em que
2006–2022 baixaram normalmente).

**Impacto:** candidaturas de 1998 e 2002 tem `total_bens_declarados = 0` e
`declarou_algum_bem = false` — o que significa "a fonte nao publica", e nao
"o candidato nao tinha bens". Qualquer comparacao de patrimonio ao longo do tempo
tem de comecar em 2006.

**Como fechar:** nao fecha. O dataset nao foi publicado. Os layouts de 1998 e 2002
declaram `indisponivel` para `bens`, e a ingestao pula com aviso em vez de falhar.

---

## L-15 · Datas de nascimento erradas no cadastro do TSE

**O que falta:** nada a obter — sao erros de digitacao na fonte.

**Impacto:** 21 candidaturas em 180.718 (0,01%) tem data de nascimento que produz
idade impossivel, conferido em 27/08/2026:

- uma com `7953-09-05` (ano 7953), que da' idade de -5.946 anos;
- quinze de 1998 com nascimento no proprio ano da eleicao, oito delas no DF com a
  mesma data (18/08/1998) — a data de registro vazou para o campo de nascimento;
- uma de 2002 nascida em 1996 (7 anos na posse) e uma de 2010 nascida em 2003 (8).

Nenhuma e' possivel: a idade minima constitucional e' 18 anos.

**Como o projeto trata:** nao corrige e nao descarta a candidatura.
`idade_na_posse` guarda o valor como a fonte publica, `idade_plausivel` marca o
caso, e `idade_na_posse_valida` (NULL quando implausivel) e' o que alimenta as
medidas de perfil. O teste `assert_idade_implausivel_e_rara` falha se a proporcao
passar de 0,5% — patamar que so' um bug de parsing alcanca.

**Como fechar:** nao fecha. Corrigir exigiria inventar a data certa.

---

## L-16 · O TSE nao publica o resultado de 2006 no cadastro de candidaturas

**Estado:** parcialmente fechada em 29/08/2026 (ADR-023) · **Fonte:** S1

O `consulta_cand` traz `DS_SIT_TOT_TURNO = '#NULO#'`, `cd = -1`, para **todos os 8
candidatos a Presidente de 2006**. Nao e' so' 2006 nem so' Presidente: sao 13.834
candidaturas de 1998-2022 sem resultado publicado.

### O que isso causou

O macro `foi_eleito` fazia `COALESCE(..., FALSE)`, e a ausencia virava afirmacao.
A ficha do Lula, publicada em `datadubaintel.com/dossie`, dizia:

    2006 · Presidente · BR · PT · Nao eleito

Ele foi eleito, em segundo turno, com 58.295.042 votos. **Nenhum teste pegou** —
`dbt build` verde, 238 testes — e quem viu foi o usuario, abrindo a propria
pagina. Foi tambem por isso que nao havia Presidente de 2006 em `fct_mandato`, e
o segundo mandato do Lula (2007-2010) nao aparecia no bloco socioeconomico.

### O que fechou

`foi_eleito` passou a ter tres estados, e onde o TSE nao publica o resultado de
cargo **majoritario** ele e' apurado dos votos oficiais + vagas em disputa
(ADR-023). Conferido contra os anos publicados: 2.636 acertos em 2.640, 50 de 50
em Presidente.

### O que continua aberto

**Cargo proporcional.** Deputado sem resultado publicado segue sem resultado, e
vai seguir: cadeira proporcional depende de quociente e sobras, nao de quem teve
mais voto pessoal. Apurar ali produziria lista errada com cara de certa.

**1998.** Nao ha' votacao de 1998 no lake, entao nao ha' o que apurar. A regra
devolve `NULL` em vez de chutar — com votos zerados, todos empatam em primeiro.

## L-17 · Plataforma de governo nao esta no portal de dados abertos

**O que falta:** um pacote em lote das propostas de governo. Conferido em
27/08/2026 com cabecalho de requisicao valido (ver L-18): quatro caminhos
plausiveis em `cdn.tse.jus.br/estatistica/sead/odsele/` retornam **404**,
inclusive para 2022 — nao e' questao de o ano ser recente.

As propostas existem, mas vivem no **DivulgaCandContas**, o sistema de consulta
individual, como PDF por candidato. Nao ha' download em lote.

**Impacto:** o SPEC 2.2 ja' colocava "propostas de governo (texto livre)" fora do
escopo. Esta conferencia mostra que o custo tambem e' maior do que parecia:
seria uma requisicao por candidato, e nao um `.zip` por ano.

**Dimensao real:** a proposta so' e' exigida por lei de cargos MAJORITARIOS —
Presidente (13), Governador (198) e Senador (318) em 2026. Sao **529 de 20.765
candidaturas (2,5%)**. Os 19.361 candidatos a deputado nao tem proposta nenhuma.
Qualquer tela que trate o campo como padrao fica vazia em 19 de cada 20 fichas.

**Como fechar:** fase propria, com decisao consciente de raspar 529 PDFs do
DivulgaCandContas, e exibicao restrita a majoritarios com rotulo explicito de
"nao se aplica a este cargo" para os demais.

---

## L-18 · O WAF do TSE recusa requisicao com cabecalho incompleto

**O que era:** o CDN do TSE responde **403** a requisicoes que nao trazem o
conjunto completo de cabecalhos de um navegador. Nao basta `User-Agent`.

Medido em 27/08/2026, mesma URL, mesmo minuto:

| Requisicao | Resposta |
|---|---|
| So' `User-Agent` de navegador | 403 |
| + `Accept`, `Accept-Language`, `Referer`, `Sec-Fetch-*`, `sec-ch-ua`, `Upgrade-Insecure-Requests` | **206 OK** |

**Como apareceu:** o primeiro pipeline no GitHub Actions falhou com 403 na
PRIMEIRA requisicao. Parecia bloqueio de IP de datacenter — hipotese que teria
levado a solucoes caras e erradas (runner auto-hospedado, proxy). Era o formato
da requisicao. Varios "rate limits" atribuidos ao CDN durante o desenvolvimento
foram provavelmente a mesma coisa.

**Estado:** resolvido em `ingest/common/http.py`, com pausa de 2s entre downloads.
Fica registrado porque, se o TSE apertar a regra de novo, o sintoma sera' 403 e a
primeira suspeita deve ser esta — nao o IP.

---

## L-19 · Votos sem quebra por municipio

**O que falta:** a votacao chega ao warehouse agregada por candidatura x turno x
UF. A fonte (`votacao_candidato_munzona`) tem grao municipio x zona x voto em
transito, e os arquivos estao baixados (~2 GB, sete eleicoes).

**Por que foi agregado:** sao ~10 milhoes de linhas por eleicao, ~70 milhoes no
total. Subir isso cru contraria a Constituicao secao 5 (custo perto de zero) e o
ADR-002 (Power BI em Import mode sobre tabelas agregadas).

**Impacto:** da' para responder "onde o candidato foi mais votado" **por estado**
(`fct_votacao_uf`), mas nao por municipio. Um mapa municipal da eleicao
presidencial, por exemplo, nao e' possivel hoje.

**FECHADA em 28/08/2026**, com escopo ainda mais estreito que o previsto:
`fct_votacao_municipio` cobre Presidente (1) e Governador (3) — **752.232 linhas**
nas sete eleicoes. Senador ficou de fora: e' majoritario, mas o mapa municipal de
uma disputa estadual acrescenta pouco ao que `fct_votacao_uf` ja' mostra.

O filtro declarativo (`filtrar` no layout) descartou 1,8 milhao de linhas so' em
2002. Sem ele, seriam ~70 milhoes de linhas somando tudo.

**Continua fora:** votos por municipio para cargos proporcionais. Sao dezenas de
milhares de candidatos a deputado espalhados por centenas de municipios cada, e o
mapa municipal de uma eleicao proporcional e' ruido, nao informacao.

---

## L-20 · FECHADA em 02/09/2026 — o Senado tem atividade legislativa

**Situacao:** FECHADA. A condicao que ela impunha foi cumprida: existe
equivalente estruturado ao `proponente` da Camara — `documento.autoria[].ordem`,
sendo `ordem = 1` o autor principal. Foi validado contra o campo oficial
`IndicadorAutorPrincipal` do endpoint antigo em 48 comparacoes nas duas direcoes,
sem divergencia. Ver F-22 e `ingest/senado.py`.

O texto original fica abaixo, porque o risco que ele descreve continua real e e'
o motivo de o filtro existir.

**Situacao original:** ABERTA · registrada em 28/08/2026

A F-16 cobre **so' a Camara**. Os 81 senadores tem a ponte de identidade (F-15) e
aparecem em `dim_parlamentar`, mas nao ha' nenhuma proposicao, relatoria ou voto
deles em `fct_atividade_legislativa`.

**Por que:** a Camara publica arquivos anuais em bloco com a marca `proponente`,
que e' exatamente o filtro que separa autoria de assinatura de apoio. O Senado
publica por API, sem equivalente em bloco, e o campo de autoria tem outra
estrutura. Replicar o mesmo rigor exigiria uma sondagem propria.

**O risco de fechar mal:** montar uma contagem de proposicoes do Senado sem
equivalente ao filtro `proponente` produziria numeros que PARECEM comparaveis aos
da Camara e nao sao. Um senador com 200 assinaturas de apoio apareceria ao lado de
um deputado com 200 projetos proprios, na mesma coluna, com o mesmo rotulo. Melhor
a ausencia explicita do que a comparacao falsa.

**Como a tela deve se comportar enquanto isso:** a pagina de Senado nao mostra
contagem de atividade — nem zerada. Zero e' uma afirmacao; ausencia de secao nao e'.

---

## L-21 · Metade das proposicoes nao tem situacao publicada

**Situacao:** ABERTA (limite da fonte) · registrada em 28/08/2026

Em 2025, **58.385 de 109.582** proposicoes com deputado proponente (53%) vem com
`ultimoStatus_descricaoSituacao` em branco no arquivo da Camara.

**Impacto:** para mais da metade das proposicoes nao da' para dizer se esta' em
tramitacao, arquivada ou virou lei.

**O que o projeto faz:** `qt_destino_desconhecido` e' uma coluna separada de
`qt_em_tramitacao` em `fct_atividade_legislativa`. Ausencia de informacao nunca e'
contada como andamento — a diferenca entre "ainda tramita" e "nao sabemos" e'
justamente o que um painel apressado apagaria.

---

## L-22 · FECHADA — orcamento federal trocado para o RTN

**Situacao:** **fechada** em 28/08/2026 · ver [ADR-017](adr/ADR-017-orcamento-federal-pelo-rtn.md)

### O que estava errado

O projeto media o orcamento federal pela DCA do SICONFI, a mesma fonte dos
estados. A receita da DCA inclui **operacoes de credito** — divida emitida para
cobrir o deficit, contada como receita. Na Uniao de 2020 foram R$ 1.647,9 bi, 45%
do total. Receita menos despesa tendia a zero por identidade contabil.

| Ano | Serie antiga (DCA) | Resultado primario real |
|---|---|---|
| 2020 | -48 bi | **-743 bi** |
| 2025 | **+635 bi de superavit** | **-61,7 bi de deficit** |

O numero estava corretamente extraido da fonte. Errado era o ROTULO — e nenhum
teste pega esse tipo de erro.

### O que substituiu

`RECEITA_LIQUIDA_UNIAO`, `DESPESA_PRIMARIA_UNIAO` e `RESULTADO_PRIMARIO_UNIAO`,
do **Resultado do Tesouro Nacional**, tabela 2.1. Serie de **1997 a 2025** — 29
anos, contra os 11 da DCA, cobrindo sete mandatos presidenciais em vez de dois.

Conferido: 2020 = -743,3 bi, 2022 = **+46,4 bi de superavit**, 2023 = -228,5 bi.
O ano com superavit importa: uma serie que so' produzisse deficit nao teria como
ser conferida.

### O que NAO mudou

Os estados continuam no SICONFI. Operacoes de credito la' sao 1,1% da receita em
SP, 0,1% no RJ e 0,2% no MA — a conta vale.

### Como isso foi descoberto

Gerando insights de exemplo, conferindo um numero contra a realidade. Passou por
`dbt build` verde, 205 testes e uma revisao de codigo sem ser notado.

Virou regra: **antes de publicar um indicador, comparar ao menos um ano com um
valor conhecido de fora do pipeline.**

---

## L-23 · Candidaturas somem da publicacao do TSE

**Situacao:** ABERTA (comportamento da fonte) · registrada em 28/08/2026

**Correcao do diagnostico inicial.** A primeira leitura foi "o pacote de fotos
esta' adiantado em relacao ao de candidatos". Errado: as candidaturas em questao
JA' ESTIVERAM no `consulta_cand` — o snapshot as capturou nas versoes 2 e 3 — e
depois **desapareceram** da publicacao. Nao e' foto adiantada, e' candidatura
retirada.

O que se via em 28/08/2026, com as duas cargas do mesmo dia:

```
pacote de fotos     20.784 candidaturas   (extraido 16:01 UTC)
consulta_cand       20.765 candidaturas   (extraido 15:34 UTC)
                        19 fotos sem candidato correspondente (0,09%)
                         4 dessas ja' tinham historico no snapshot
```

As mesmas chaves aparecem nos dois sintomas — `10002554293` e `10002554295` (AC),
`90002554305` (GO), `120002554294` (MS). Recarregar o `consulta_cand` NAO as
trouxe de volta: elas nao estao mais la'.

**Por que isso importa mais do que parece.** O TSE publica sempre o ESTADO ATUAL,
sem historico. Quem le' a publicacao de hoje nunca fica sabendo que aquelas
candidaturas existiram. O snapshot diario e' a unica coisa que guarda esse fato, e
ele e' **irreproduzivel depois de 04/10/2026**.

**O que mudou por causa disto:**

1. `fct_mudanca_candidatura` ganhou `consta_na_lista_atual`. FALSE = existiu e
   sumiu. A tela precisa dizer "nao consta mais na lista do TSE" em vez de exibir
   a candidatura como se fosse atual.
2. O teste de relacionamento com `fct_candidatura` saiu — tratava um evento real
   como quebra de integridade. No lugar entrou
   `assert_sumico_de_candidatura_e_raro`, com teto de 2%.
3. `assert_foto_sem_candidatura` passou de ZERO orfas para teto de **1%**. Foto
   orfa e' inofensiva na tela (`dim_candidato` faz LEFT JOIN, entao ela nao
   aparece), e exigir zero deixaria o pipeline diario vermelho ate' 04/10/2026 —
   e pipeline que vive vermelho para de ser lido.

Os dois tetos continuam protegendo o caso grave: erro de `sk_candidatura`, ou
carga truncada, nao produz 0,1% de divergencia — produz dezenas de por cento.

**Como fechar:** nao fecha. E' o comportamento da fonte, e capturá-lo e' um dos
motivos de o projeto existir.

---

## L-24 · Dois tercos das candidaturas ainda nao prestaram contas

**Estado:** aberta, e fecha sozinha · **Fonte:** S18 · **Medido em:** 28/08/2026

7.722 das 20.765 candidaturas de 2026 constam na prestacao de contas eleitorais.
As outras 13.043 nao declararam **nada** — o que nao e' o mesmo que declarar zero.

O prazo legal de prestacao e' posterior a 04/10/2026. Ate' la' o TSE republica o
pacote conforme as campanhas entregam, e a cobertura sobe a cada carga diaria.

**Por que isto e' uma lacuna e nao um bug:** o numero esta' certo; e' o calendario
que ainda nao chegou. O erro possivel nao esta' no dado, esta' na **tela** — se a
ficha de quem nao prestou contas mostrasse "R$ 0,00", afirmaria campanha sem
dinheiro onde ha' apenas prazo em aberto. A propria pagina do TSE faz isso hoje:
mostra `Despesas R$ 0,00` para campanhas presidenciais milionarias.

**Como o projeto trata:** `Candidato.financiamento` fica em lista vazia e o bloco
escreve *"prestacao ainda nao entregue"*. Nenhuma linha zerada e' fabricada em
lugar nenhum do pipeline — nem no `raw`, nem no mart, nem na ficha. E' a mesma
distincao da ADR-013 entre "nao apresentou plano" e "nao e' exigido plano".

**Quando fecha:** depois de 04/10/2026, com a prestacao final. A cobertura de hoje
ja' e' verificavel: o total de uma candidatura confere ao centavo com a pagina
oficial (ADR-020, seccao Verificacao).

---

## L-25 · Relatoria no Senado nao e' atribuivel ao senador

**Situacao:** ABERTA · registrada em 02/09/2026

A F-22 trouxe a atividade do Senado com as mesmas quatro classes da Camara, mas
uma delas vem sempre vazia: **relatoria**. Sao ZERO linhas em 57.170.

**Por que:** no Senado o parecer e' documento dentro da tramitacao de uma
materia, nao uma materia com autoria propria. A consulta por sigla confirma:
`/processo?sigla=PAR&ano=2025` devolve zero. Na Camara o parecer E' proposicao
(PRL, PAR, SBT) e por isso aparece la'.

**Impacto:** um senador relata constantemente, e a ficha nao mostra nada disso. A
leitura errada seria concluir que ele nao relatou — por isso o bloco DIZ que a
ausencia e' da fonte, e nao da pessoa (ADR-031: ausencia nomeada, nunca
silenciosa).

**Como fechar:** exigiria percorrer a tramitacao de cada materia atras do
relator designado, o que e' outra ordem de grandeza de requisicoes e outra
fonte de verdade. Nao foi tentado.

**O que NAO fazer:** preencher com o numero de relatorias da Camara, ou somar as
duas casas. Sao coisas diferentes e a tela ja' avisa que nao se comparam.

---

## L-26 · Estado sem indicador de resultado fiscal

**Situacao:** ABERTA · registrada em 03/09/2026

Ate' 03/09/2026 havia `RESULTADO_ORCAMENTARIO`, calculado como receita menos
despesa. Ele foi RETIRADO (ADR-035): a receita passou a ser a Receita Corrente
Liquida, que e' receita CORRENTE, e a despesa e' empenhada TOTAL, com capital.
Subtrair as duas produziria um deficit estrutural que nao existe.

**O substituto obvio nao serve por cobertura.** O RREO Anexo 6 publica
`RESULTADO PRIMARIO (COM RPPS)`, padronizado e oficial — seria o espelho exato do
`RESULTADO_PRIMARIO_UNIAO` que ja' mostramos para o governo federal. Medido em
03/09/2026: a conta so' aparece **a partir de 2023**. Nos anos anteriores o
rotulo do anexo era outro.

Tres anos nao cobrem uma janela de mandato de quatro. Um indicador que existe
so' no fim da janela produziria variacao sobre um ponto — ou nenhuma.

**Como fechar:** mapear os rotulos do Anexo 6 nas versoes antigas do RREO
(2015-2022) e conferir que a conta e' a mesma. E' sondagem propria, do mesmo
tamanho da que fechou a L-20.

**O que NAO fazer:** voltar a subtrair receita de despesa. Foi assim que MG 2023
apareceu com superavit de R$ 24 bilhoes.

---

## L-27 · O arquivo de bens de 2006 publica valores zerados

**Situacao:** ABERTA · registrada em 03/09/2026

**O que falta:** valor de bem no arquivo `bem_candidato` de 2006. Medido em
03/09/2026, sobre 509.450 itens de todos os anos:

| ano | itens | zerados | candidaturas | somam zero |
|---|---|---|---|---|
| 2006 | 82.361 | 8.506 (10,3%) | 19.263 | **6.699 (34,8%)** |
| 2010 | 81.226 | 0 (0,0%) | 13.545 | 0 |
| 2014 | 83.053 | 4 (0,0%) | 15.300 | 0 |
| 2018 | 93.527 | 4 (0,0%) | 17.646 | 1 |
| 2022 | 92.559 | 410 (0,4%) | 18.249 | 26 |
| 2026 | 76.724 | 261 (0,3%) | 13.831 | 14 |

Um terco de 2006 contra praticamente nada em todos os outros anos nao e' um fato
sobre as pessoas de 2006 — e' um fato sobre o arquivo daquele ano. E' o segundo
problema conhecido dele; o primeiro e' a [L-16](#l-16), o desfecho da eleicao que
ele nao publica.

**Impacto:** `fct_patrimonio_declarado` deixaria "R$ 0 em 2006" ao lado de
"R$ 500 mil em 2026" na mesma ficha, e o leitor concluiria uma historia que o
dado nao conta.

**Como esta' tratado:** o modelo corta declaracao cujo total e' zero
(`having max(vl_total) > 0`), e o teste
`assert_patrimonio_zero_nao_publicado` trava a volta do filtro. Quem nao declarou
nada nao tem linha; quem declarou zero tambem nao, porque zero ali nao quer dizer
zero.

**O que NAO fazer:** publicar o zero como patrimonio. Seria ausencia virando
afirmacao, sobre uma pessoa real, exatamente o que a Regra 5 proibe.

**Como fechar:** ler o `leiame` do pacote de 2006 e conferir se o valor esta' em
outra coluna naquele ano, como ja' aconteceu com o layout de candidaturas (L-01).

---

## L-28 · Comissões do Senado não têm em quem aparecer

**Situacao:** FECHADA em 05/09/2026 · ADR-048 · F-29

**Por que ela estava errada.** A premissa desta lacuna era que exibir comissao de
senador exigiria `casamento_confiavel`, e que sem CPF o bloco "nao teria em quem
aparecer". A premissa nao se sustentou: o bloco de **atividade legislativa do
Senado** ja' estava no ar desde a F-22 com exatamente a mesma identidade inferida
e uma ressalva na tela (ADR-034), e aparecia em 50 fichas de 2026.

Ou seja, o projeto ja' tinha decidido como tratar identidade inferida no Senado.
Esta lacuna aplicava a comissao um criterio mais duro que o que o proprio site
usava duas secoes acima — e o custo disso nao era prudencia, era um bloco a menos
por uma regra que nao existia.

Fechada com `fct_comissao_senador`: filtro `id_pessoa is not null`, com
`casamento_confiavel` e `metodo_id_pessoa` viajando ate' a tela, e a ressalva
escrita no topo do bloco. **51 fichas de 2026** passaram a mostrar o bloco.

O que a L-28 acertou continua valendo e virou ressalva visivel em vez de omissao:
a identidade e' por nome + nascimento, forte e nao certa, e quem le' precisa
saber disso.

Duas coisas que a fonte nao da' viraram a **L-30**, aberta no lugar.

<details><summary>Registro original, de 04/09/2026</summary>

**Situacao:** ABERTA · registrada em 04/09/2026

**O que falta:** o bloco de comissoes (F-26) cobre so' a Camara. A API do Senado
tem `/senador/{codigo}/comissoes` e o dado existe — o que falta nao e' a fonte, e'
a IDENTIDADE.

Medido em 04/09/2026 em `dim_parlamentar`:

| casa | parlamentares | com `id_pessoa` | com `casamento_confiavel` |
|---|---|---|---|
| camara | 1.991 | 1.991 | **1.991** |
| senado | 81 | 80 | **0** |

O Senado nao publica CPF, entao o casamento e' por nome + data de nascimento
(ADR-014) e nenhum senador chega a `casamento_confiavel`. Coletar as comissoes
deles produziria um bloco que nao poderia ser exibido em ficha nenhuma sem risco
de atribuir um assento a um homonimo.

**Impacto:** a ficha de senador nao mostra comissao. A de deputado mostra. A
diferenca e' visivel e nao esta' explicada na tela para o leitor — este e' o
custo aberto.

**Como fechar:** a mesma sondagem que fechou a L-20. Se o Senado publicar CPF em
algum endpoint, ou se houver outra chave forte (titulo de eleitor nao serve —
LGPD), o casamento passa a ser confiavel e o bloco vem junto.

**O que NAO fazer:** exibir com casamento por nome. Homonimia com mesma data de
nascimento e' improvavel, nao impossivel, e o custo do erro aqui e' atribuir a
uma pessoa o assento de outra.

</details>

---

## L-29 · 17% das emendas o Portal publica sem autor

**Situacao:** ABERTA · registrada em 04/09/2026 · **nao e' lacuna deste projeto**

**O que falta:** o autor de 15.962 das 94.463 linhas do arquivo de emendas
parlamentares do Portal da Transparencia. O campo vem preenchido com
`Sem informação`.

| | linhas | |
|---|---|---|
| autor individual identificado | 73.856 | 78% |
| **autoria nao publicada** | **15.962** | **17%** |
| relator geral, bancada, comissao | 4.645 | 5% |

Sao **R$ 18,5 bilhoes pagos** que a fonte nao atribui a ninguem.

**Impacto:** o bloco de emendas na ficha mostra apenas o que a fonte atribui.
Sem dizer isso, ele sugeriria que a lista esta' completa — e um leitor concluiria
que o parlamentar so' moveu o que aparece ali.

**Como esta' tratado:** a tela diz, com numero, quanto o Portal nao atribui. As
linhas continuam em `stg_transparencia__emendas`, marcadas com
`autoria_nao_publicada`, para que a contagem possa ser refeita.

**Como fechar:** nao esta' ao alcance deste projeto. A autoria existe no SIOP e
nas atas da Comissao Mista de Orcamento; o Portal e' que nao a publica no arquivo
em bloco. Fechar exigiria outra fonte, com outro casamento de identidade.

**O que NAO fazer:** distribuir o valor sem autor entre os autores conhecidos,
por rateio ou por qualquer criterio. Seria inventar autoria de dinheiro publico.

---

## L-30 · O Senado não publica presidência de comissão, nem a Mesa Diretora

**Situacao:** FECHADA em 05/09/2026, no mesmo dia em que foi aberta · ADR-049 · F-31

**A medicao estava certa e a conclusao estava errada.** Em 7.226 vinculos de
`/senador/{codigo}/comissoes` ha' mesmo zero presidencias e nenhuma Mesa. O que
nao se seguia dali e' que o Senado nao publique o dado — ele publica, em outra
rota da mesma API:

    /senador/{codigo}/cargos.json

Ela devolve PRESIDENTE, VICE-PRESIDENTE, RELATOR, SECRETARIO e CORREGEDOR, com
colegiado e periodo, e traz junto os colegiados que a outra rota nao conhece —
Mesa Diretora do Congresso Nacional e Comissao Diretora do Senado Federal.

O erro foi de metodo: procurei a Mesa por rotas plausiveis (`composicao/mesa`,
`plenario/lista/mesa`, `composicaoMesa`, `senador/lista/mesa`, todas vazias) e
nao pelo caminho que a propria API ja' usava para todo o resto, que e' pendurar o
recurso no parlamentar.

Fechada com 804 cargos de comando e 61 vinculos de Mesa onde havia zero.
Conferida pela invariante mais forte que o dado admite: **uma presidencia por
colegiado em cada momento** — 18 permanentes e a Mesa, um presidente cada, zero
duplicados.

**O que fica como aprendizado, e nao como lacuna:** medir a ausencia numa rota
nao prova a ausencia na fonte. Esta lacuna sobreviveu um dia porque a medicao
parecia conclusiva demais para ser questionada.

<details><summary>Registro original, de 05/09/2026</summary>

**Situacao:** ABERTA · registrada em 05/09/2026 · **nao e' lacuna deste projeto**

**O que falta:** duas coisas que a ficha de deputado tem e a de senador nao pode
ter, porque a fonte nao as devolve.

**1. Nao ha' papel de comando.** A rota `/parlamentar/{codigo}/comissoes` devolve
tres papeis, e so' tres. Medido em 05/09/2026 sobre 7.226 vinculos:

| papel | vinculos |
|---|---|
| Titular | 4.708 |
| Suplente | 2.516 |
| Nato | 2 |
| **Presidente, Vice, Relator** | **0** |

Na Camara, `/deputados/{id}/orgaos` traz o `titulo` e por isso a ficha diz quem
presidiu a CCJC. No Senado esse dado nao existe por este caminho.

**2. Nao ha' Mesa Diretora.** Nenhum dos 7.226 vinculos tem classe `mesa` — a
Mesa nao e' "comissao" no modelo de dados do Senado. O efeito e' concreto e
visivel: **Davi Alcolumbre preside o Senado, e a ficha dele mostra apenas o
Conselho de Etica.** Nao ha' rota aberta que devolva a composicao da Mesa:
`composicao/mesa`, `plenario/lista/mesa`, `composicaoMesa` e `senador/lista/mesa`
respondem vazio (135 a 145 caracteres).

**Impacto:** a ficha de senador tem uma tabela de assentos sem hierarquia. Um
leitor que compare as duas casas lado a lado pode concluir que o senador nunca
presidiu nada — quando o que houve foi silencio da fonte, nao ausencia do fato.

**Como esta' tratado:** o bloco de comissoes no Senado diz, com todas as letras,
que presidencia e relatoria nao aparecem e que isso nao significa que nao houve,
e cita esta lacuna com link. A alternativa — deduzir presidencia de outra rota,
ou herdar do titulo do parlamentar — inventaria o dado (Regra 5).

**Como fechar:** as atas de instalacao de cada comissao trazem a eleicao do
presidente, e a pagina publica de cada colegiado exibe a Mesa. As duas exigiriam
raspagem de HTML renderizado por JavaScript — a pagina
`legis.senado.leg.br/comissoes/comissao?codcol=34` volta com 57 KB de casca e a
composicao carregada depois. Fica fora do custo quase-zero do projeto por ora.

**O que NAO fazer:** preencher o papel com "Titular" onde a pessoa presidiu, ou o
contrario. E nao inferir a Mesa a partir do cargo declarado no perfil do senador:
o cargo e' do presente e o assento tem periodo, e cruza-los produziria a
afirmacao de que ele presidiu a Casa durante todos os mandatos.

</details>

---

## L-31 · A presidência de um colegiado pode existir e não poder ser exibida

**Situacao:** FECHADA em 05/09/2026, no mesmo dia em que foi aberta · ADR-050

**O diagnostico estava errado, e a saida proposta nao teria funcionado.** Esta
lacuna dizia que a presidencia da CRA nao aparecia por HOMONIMIA, e propunha usar
a UF como desempate. As duas identidades que respondem pela chave de Zequinha
Marinho sao ambas do PA — a UF nao desempataria nada.

O que havia era outra coisa: `id_pessoa` e' o `cpf_hash` quando o ano publica CPF
e a chave de nome quando nao publica (ADR-005). O CPF cobre 100% de 2006, 2010 e
2026, mas **96,9% de 1998** — e a mesma pessoa fica com DOIS `id_pessoa` quando
tem candidatura dos dois lados dessa fronteira. Contar identidades distintas leu
isso como duas pessoas.

Medido em 05/09/2026 sobre 131.567 chaves: das 326 com mais de um `id_pessoa`,
**210 sao fronteira** (uma identidade com CPF e uma sem) e 116 sao homonimia de
verdade. Das 210, 204 nao tem um unico ano em comum entre os dois ids.

Fechada contando so' identidades COM CPF para decidir a ambiguidade. Nao funde
ninguem: o `id_pessoa` de cada candidatura continua o que era. Duas identidades
com CPF na mesma chave seguem sendo duas pessoas, e a chave segue recusada.

<details><summary>Registro original, de 05/09/2026</summary>

**Situacao:** ABERTA · registrada em 05/09/2026 · **e' o residuo honesto da L-28**

**O que falta:** identidade. A rota de cargos publica quem preside cada
colegiado, mas exibir isso exige ligar o senador a' pessoa que se candidata — e
essa ligacao e' por nome + data de nascimento, sem CPF (ADR-034).

Quando o nome casa com mais de uma pessoa do cadastro eleitoral,
`metodo_id_pessoa` fica `ambiguo`, `id_pessoa` fica nulo, e o vinculo NAO entra
no mart.

Medido em 05/09/2026: das 19 presidencias em curso de comissao permanente e
Mesa, **uma** nao pode ser exibida — a da Comissao de Agricultura e Reforma
Agraria, de Zequinha Marinho.

**Impacto:** a CRA aparece na ficha sem presidencia atual, e nao ha' nada na tela
dizendo que ha' uma e que ela e' de outra pessoa. O leitor que compare a ficha
com a pagina do Senado encontra a diferenca sem explicacao.

**Como esta' tratado:** o vinculo fica de fora. Atribuir a presidencia da CRA a
um homonimo seria o pior erro possivel nesta tela — pior que a ausencia.

**Como fechar:** a UF esta' disponivel dos dois lados do casamento e ainda nao e'
usada como criterio de desempate. Um senador do Para e um candidato de outro
estado com o mesmo nome e nascimento deixariam de ser ambiguos. E' trabalho no
`dim_parlamentar`, nao nesta feature.

**O que NAO fazer:** escolher "o mais provavel" entre os homonimos por votacao,
partido ou qualquer heuristica. Ou a ligacao e' segura ou o dado nao aparece.

</details>
