# ADR-044 — Comissões da Câmara: onde o deputado trabalha

**Status:** Aceita · **Data:** 2026-09-04 · **Relacionada:** F-26, ADR-014, ADR-034, Constituição §0.1

## Contexto

A ficha dizia quantas proposições o deputado apresentou e quantas vezes votou.
Não dizia **onde** ele trabalha. Comissão permanente é onde a maior parte do
trabalho legislativo acontece de verdade, e assento no Conselho de Ética ou na
Mesa Diretora é fato público que muda como se lê o resto da ficha.

## Três coisas que a fonte faz e que quase produziram dado errado

### 1. O endpoint só devolve o presente, a menos que se peça o passado

`/deputados/{id}/orgaos` **sem parâmetro** devolve quase nada. Arthur Lira, que
**presidiu a Câmara**, volta com **um** vínculo — uma bancada de 2023. Com
`dataInicio=2003-02-01&dataFim=2027-01-31`, volta com **41**, de 2011 a 2025.

Sem as datas, a ficha de quem presidiu a Casa diria que ele participou de um
órgão só. Ausência virando afirmação.

### 2. O catálogo padrão de órgãos é incompleto, e o que falta é o que importa

`/orgaos` sem parâmetro devolve 1.649. Parece o catálogo inteiro, e não é:
medido em 04/09/2026, **370 órgãos citados por apenas 25 deputados** não estavam
nele. Com `dataInicio=2003-01-01` sobe para 2.230 e a falta cai para 5%.

Os 5% que sobram são justamente:

```
4     MESA       Mesa Diretora
5467  PRESI      Presidência
5971  COETICA    Conselho de Ética e Decoro Parlamentar
6087  CEXSAUDE   Comissão Externa
```

Órgãos permanentes da Casa, cuja data de início a API não publica de forma que o
filtro alcance. Sem tratar, o assento de maior peso público sumiria da ficha — e
o log diria apenas "N órgãos fora do catálogo", que ninguém lê.

O resolvedor tem duas etapas: catálogo com janela (23 requisições) e, para o que
sobrar, uma consulta por órgão com **cache em disco**. Órgão não muda de tipo; a
segunda execução não pede nenhum de novo. Efeito medido: os vínculos
classificados como colegiado subiram de **545 para 1.060** na mesma amostra.

### 3. O nome do tipo de órgão não é confiável

`codTipoOrgao = 15` chama-se oficialmente **"COORDENADORIA DA MULHER"**. Os 13
órgãos com esse código são: CDMULHER, SEMULHER, SECOM, SRI, SEJUVE, SETRANSP,
SEMIDIA, CONMP, **BANEGRA** (Bancada Negra), SEEMPLEG, SEINOLEG, SEDEFPAR,
SESIDH.

O código agrupa secretarias, coordenadorias e bancadas, e o nome do balde é o da
primeira coisa que entrou nele. Renderizar `tipoOrgao` como veio diria que a
**Bancada Negra é a "Coordenadoria da Mulher"**.

É o mesmo erro que a L-20 quase publicou (ADR-034): o **código** é confiável, o
**nome do código** não é. Este projeto classifica pelo código e escreve o rótulo
em português uma vez, em `ingest/comissoes.py`.

## Decisão

`fct_comissao_deputado`: um colegiado por linha, com os períodos somados.

**Por que somados.** A Câmara renova a composição todo ano, e o mesmo deputado
reaparece na mesma comissão a cada renovação: 25 deputados produziram **490
assentos em comissão permanente**, quase todos repetindo o mesmo colegiado.
Listar as 490 seria enterrar a informação no próprio volume. Somadas por órgão,
viram "CCJC — Presidente, 2007–2026".

**O papel mostrado é o de maior peso.** Quem presidiu num ano e foi suplente
noutro aparece como Presidente. Não é juízo sobre a pessoa: é escolher, entre
fatos igualmente verdadeiros, o mais informativo — como a trajetória mostra o
resultado do turno decisivo e não a soma dos turnos. A ordem é a hierarquia
**formal** do colegiado, e a tela explica o critério para ninguém entender que
foi Presidente o tempo todo.

## O que fica de fora, e por quê

**Filiação a partido, bloco, liderança e bancada.** A tabela de tipos da API
declara essas espécies como "órgão", e por isso o classificador as reconhece e
as mantém fora da promoção a colegiado — estar no PT não é ter assento na CCJ.

**Medição posterior, registrada por honestidade:** nenhum órgão desse tipo
apareceu entre os 79.140 vínculos coletados, nem no catálogo com janela desde
2003. A salvaguarda existe e **não precisou agir**. A versão anterior deste ADR
dizia que ela filtrava vínculos partidários; isso não se confirmou, e afirmar um
efeito que não aconteceu é o mesmo defeito que este projeto persegue no dado.

**Comissão de medida provisória.** São 1.393 no catálogo, e participar delas é
rotina; quarenta linhas "Comissão da MPV 936" afogariam as que importam.

**O Senado.** A API do Senado tem `/senador/{codigo}/comissoes` e o dado existe,
mas nenhum senador tem `casamento_confiavel` — a Casa não publica CPF (ADR-014),
e o bloco não teria em quem aparecer sem risco de homônimo. Fica registrado como
lacuna, não como esquecimento.

## Só quem tem identidade confirmada

`casamento_confiavel` é o filtro. Na Câmara ele significa casamento por **CPF**.
Sem ele, um assento na CCJ poderia ser atribuído a um homônimo — uma afirmação
falsa publicada sobre uma pessoa real.
