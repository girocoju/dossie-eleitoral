# Lacunas conhecidas

> SPEC secao 9: "Ao encontrar dado ausente em uma UF/ano: registrar aqui, **nao preencher**."
>
> Nenhum item desta lista e' contornado por interpolacao, media ou estimativa.
> Enquanto estiver aqui, o dado simplesmente nao existe no produto — e a tela diz isso.

Ultima revisao: **2026-08-27**

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

## L-03 · Mortalidade infantil por UF (S9)

**O que falta:** serie por UF. Conferido em 27/08/2026: o Ipeadata so' tem
`DEPIS_TMI`, de base Macroeconomica, ou seja, **apenas Brasil**. Nao ha' quebra
estadual la'.

**Impacto:** o indicador esta' no catalogo com `verificado: false` e `provedor:
arquivo`, e nao entra na carga.

**Como fechar:** extrair do DATASUS/TabNet (SIM + SINASC) por UF e ano, publicar
a URL no catalogo `indicadores.yml`.

---

## L-04 · IDHM tem tres pontos em vinte anos

**O que falta:** nada a obter — e' a natureza da fonte (2000, 2010, 2021).

**Impacto:** o IDHM **nao** entra em `fct_mandato_indicador` como variacao de
mandato. Dois pontos separados por dez anos nao descrevem uma janela de quatro.
Ele aparece so' como corte de contexto.

**Como fechar:** nao fecha. E' um limite da fonte, documentado em METODOLOGIA secao 9.

---

## L-05 · IDEB (S10) sem URL no catalogo

**O que falta:** URL do arquivo do INEP em `indicadores.yml`.

**Impacto:** indicador declarado, `ingerivel = false`, fora da carga.

**Como fechar:** preencher `parametros.url` e implementar o provedor `arquivo`
(leitura de XLSX) em `ingest/`.

---

## L-06 · Desemprego so' a partir de 2012

**O que falta:** nada a obter. A PNAD Continua comeca em 2012T1.

**Impacto:** mandatos iniciados antes de 2012 (eleicoes de 1998, 2002, 2006) nao
tem esse indicador em `fct_mandato_indicador`. O par mandato x indicador
simplesmente nao existe — nao aparece zerado.

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

## L-10 · Vinculacao de pessoa em anos sem CPF

**O que falta:** medir a taxa real por ano.

**Impacto:** onde o CPF nao existe, `id_pessoa` cai no fallback nome+nascimento e
`link_confiavel = false`. Trajetorias que dependem disso sao sinalizadas na tela.

**Como fechar:** rodar a analise `relatorio_vinculacao_pessoa` depois da carga do
historico e registrar aqui os percentuais por ano — **medidos, nao estimados**.

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

## L-16 · Resultado da eleicao presidencial de 2006 nao esta no `consulta_cand`

**O que falta:** `DS_SIT_TOT_TURNO` das oito candidaturas a Presidente de 2006 vem
vazio, e o pacote nao traz linhas de 2o turno para o cargo 1 — embora traga os 27
governadores eleitos naquele mesmo ano. Conferido em 27/08/2026.

**Impacto:** o mandato presidencial de 2007–2010 **nao existe** em `fct_mandato`.
E' o unico ciclo presidencial ausente entre 1998 e 2022. O modulo
"Durante o mandato" nao tem esse periodo no nivel Brasil.

**Como fechar:** cruzar com `votacao_candidato_munzona_2006` (S4, ver L-02), que
traz a votacao apurada, ou com a serie de resultados do proprio TSE. Ate' la', a
ausencia fica visivel na tela em vez de ser preenchida.

---

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

**Como fechar:** um fato adicional com grao municipio, restrito aos cargos
MAJORITARIOS (1, 3, 5). O volume cai de ~70 milhoes para a ordem de 1,7 milhao de
linhas — os proporcionais e' que sao caros, porque sao dezenas de milhares de
candidatos. Exige decisao de escopo, porque acrescenta uma tabela grande ao
modelo do Power BI.
