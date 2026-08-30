# ADR-024 — Atividade legislativa de mandatos anteriores

**Status:** Aceita · **Data:** 2026-08-30 · **Feature:** F-19 · **Estende:** ADR-014, ADR-015

## Contexto

A ficha mostrava atividade legislativa de **48** dos 529 majoritários de 2026.
Mas **118** deles já foram deputados federais. Os 70 que faltavam não tinham
problema de dado: as proposições deles estão nos arquivos da Câmara desde 2003.
Faltava saber **de quem eram**.

A ponte de identidade (ADR-014) só conhecia quem está em exercício hoje — 513
deputados. Quem serviu de 2003 a 2022 e saiu não tinha `id_pessoa`, então a
atividade não chegava a ficha nenhuma.

## Decisão

**Varrer as legislaturas encerradas.** A API da Câmara lista deputados por
legislatura (`?idLegislatura=`) e o detalhe traz **CPF** — inclusive de quem já
saiu. Medido em 30/08/2026, nas cinco legislaturas de 2003 a 2023:

| | |
|---|---|
| Registros | 5.023 |
| Pessoas distintas | 1.788 |
| **Sem CPF** | **0** |

CPF a 100% importa: casa com o TSE pela mesma chave do candidato, sem o risco de
homonímia que obrigou a marcar o Senado como casamento inferido.

### Carga separada, e por quê

`ingest.legislativo historico` é comando próprio, e a tabela é outra
(`parlamentares_historico`). Dois motivos:

**Custo.** Uma requisição de detalhe por deputado por legislatura — cerca de mil
por legislatura, ~50 minutos no total. Não cabe num pipeline diário.

**Imutabilidade.** Legislatura encerrada não muda. Rodar uma vez basta.

A tabela é separada porque a carga diária **substitui** `parlamentares` inteira,
e apagaria os 50 minutos de trabalho todo dia.

### Um carregador que faltava

As proposições usavam `load_ndjson`, que troca a tabela inteira. Funcionava com
2023-2026; com os anos históricos, a carga diária apagaria 2003-2022 **todo dia,
em silêncio**.

`load_intervalo` é a irmã de `load_ano` para o outro esquema de particionamento
que o projeto usa: `load_ano` serve tabela particionada por dia com decorador
`$YYYY0101`; `load_intervalo` serve particionamento por intervalo de inteiro, com
`$2011`. Trocar o esquema da tabela para agradar `load_ano` seria reescrever o
que já estava certo.

Conferido: carregar 2011 deixou 2023-2026 intactos.

## Resultado

| | Antes | Depois |
|---|---|---|
| Ponte da Câmara | 513 | **1.992** (100% casados) |
| Período | 2023-2026 | **2003-2026** |
| Proposições | 296.962 | **817.822** |
| **Majoritários com atividade** | **48** | **117** |

117 de 118 possíveis. O que falta é uma pessoa cuja passagem pela Câmara é
anterior a 2003.

## O erro que isso quase publicou

Ronaldo Caiado aparecia com **102 proposições em 2015-2017**, e ele era
**senador** naquele período.

O dado não estava errado. São emendas a Medidas Provisórias e um parecer de
relator: senador atua na comissão mista de MP, e a Câmara registra a autoria. Um
dos registros traz, com o rótulo defasado da própria fonte, *"Parecer do Relator,
Dep. Ronaldo Caiado (DEM-GO)"*.

**O erro seria do rótulo.** Apresentar aquilo sob "55ª legislatura da Câmara dos
Deputados" afirmaria um mandato que não houve — o mesmo tipo de erro do
*"2006 · Não eleito"* (ADR-023): o dado certo, a afirmação errada.

`dim_legislatura_parlamentar` diz em que legislaturas cada pessoa **realmente**
teve mandato, e a ficha separa as duas coisas: onde não houve mandato, a
atividade aparece marcada *"sem mandato de deputado neste período"*, com a
explicação ao lado.

Um segundo erro da mesma família apareceu no caminho: o modelo novo marcava todo
ex-deputado como parlamentar da 57ª legislatura, e a ficha de Caiado — governador
de Goiás — passou a dizer que ele tem mandato de deputado agora. A causa foi a
ponte histórica entrar em `dim_parlamentar` sem distinção de exercício. Daí a
coluna `em_exercicio`.

## O que a ficha mostra, e o que não mostra

**Uma tabela por legislatura**, e não um agregado. Somado, quem serviu de 2003 a
2010 e voltou em 2019 aparecia como "2003-2023", sugerindo mandato contínuo que
não houve.

**Não há taxa de presença**, e a decisão é deliberada. A API não publica; teria de
ser derivada de eventos, onde falta se confunde com comissão, missão oficial e
licença médica. Publicar "62% de presença" errado sobre uma pessoa real é a
mesma classe de erro que esta ADR corrige duas vezes. A frequência oficial existe
no portal da Câmara, fora do dado aberto — o caminho honesto seria citá-la, não
inferi-la.

**Não há votações**, ainda. A API suporta (`/votacoes` + `/votos`) e é o próximo
passo natural.

**Assembleias estaduais continuam fora.** São 27 fontes sem padrão comum. É por
isso que Flávio Bolsonaro — deputado estadual no RJ de 2003 a 2018 e senador
desde 2019 — segue sem atividade: as duas Casas por onde passou estão fora do
alcance do projeto (L-20 para o Senado).
