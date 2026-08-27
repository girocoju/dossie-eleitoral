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

## L-02 · Votos por candidato (S4) nao ingeridos

**O que falta:** `votacao_candidato_munzona_{ano}` (1998–2022). A coluna
`votos_nominais` de `fct_candidatura` existe e esta' sempre NULL.

**Impacto:** nao ha' votacao nominal no produto. Nao afeta `fct_mandato`, que
depende de `DS_SIT_TOT_TURNO` e nao da contagem de votos.

**Como fechar:** declarar o dataset `votacao` em `tse_base.yml` e agregar para
(ano, sq_candidato, UF, cargo, turno) **durante** a ingestao — o pacote tem GBs e
nao pode subir cru para o BigQuery (SPEC S4, ADR-002).

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
