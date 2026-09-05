# ADR-048 — Comissões do Senado, com identidade inferida e assumida

**Data:** 05/09/2026
**Situação:** aceito
**Fecha:** L-28 · **Abre:** L-30 · **Feature:** F-29

## Contexto

A ficha de deputado mostrava onde a pessoa sentou (F-26, ADR-044). A de senador,
não. A L-28 explicava a diferença assim: exibir comissão de senador exigiria
`casamento_confiavel`, o Senado não publica CPF, logo nenhum senador teria como
aparecer — e coletar o dado produziria um bloco sem ninguém para exibi-lo.

**A premissa estava errada, e o próprio site provava.**

O bloco de **atividade legislativa do Senado** estava no ar desde a F-22
(ADR-034), com exatamente a mesma identidade inferida — nome + data de
nascimento — e uma ressalva escrita na tela. Ele aparecia em 50 fichas de 2026.

A L-28 aplicava a comissão um critério mais duro que o que o site usava duas
seções acima, na mesma página, sobre as mesmas pessoas. Isso não era prudência:
era um bloco a menos por uma regra que o projeto não tinha.

## Decisão

**Coletar as comissões do Senado e exibi-las com o mesmo padrão de identidade
que a atividade legislativa do Senado já usa** — `id_pessoa is not null`, com
`casamento_confiavel` e `metodo_id_pessoa` viajando até a tela e a ressalva
escrita no topo do bloco.

O que a L-28 acertou continua valendo, e virou texto visível em vez de omissão: a
ligação é forte, não certa, e quem lê precisa saber com que grau de certeza o
assento foi atribuído àquela pessoa.

Resultado: **51 fichas de 2026** ganharam o bloco — uma a mais que a atividade
legislativa, e nenhuma que já não carregasse a mesma ressalva.

## O problema que apareceu no caminho: o catálogo só cobre o presente

O tipo do colegiado vem do `CodigoTipoColegiado`, que está no catálogo
`comissao/lista/colegiados.json`. Esse catálogo lista **apenas colegiado em
atividade**.

Medido em 05/09/2026: **292 colegiados** citados pelos senadores não estavam no
catálogo, e os vínculos deles — **1.483, 21% do total** — ficariam sem tipo e
fora da ficha. E o que ficava de fora era justamente o de maior peso público:

| colegiado | vínculos perdidos |
|---|---|
| CPMI do INSS | 173 |
| Comissão Representativa do Congresso Nacional | 110 |
| CPI do Crime Organizado | 40 |
| CPMI das Fake News | 35 |
| CPMI do 8 de Janeiro | 35 |
| CPI da Pandemia | 29 |

É o mesmo padrão da Câmara, onde o catálogo omitia a Mesa, a Presidência e o
Conselho de Ética (ADR-044). Aceitar a perda apagaria da ficha o assento que mais
diz sobre um mandato.

**E não há rota que resolva o passado.** Ao contrário da Câmara, o Senado não tem
detalhe por colegiado que devolva o tipo: `comissao/{codigo}` responde vazio (217
caracteres), e os parâmetros de inativos da listagem são ignorados — a resposta é
byte a byte idêntica à dos ativos.

### A saída: o nome oficial, e nunca a sigla

Sobrou o nome. `_classe_por_nome` classifica a partir da **forma oficial escrita
por extenso** — "Comissão Parlamentar Mista de Inquérito", "Comissão
Representativa do Congresso Nacional" — testando a forma mais específica antes da
mais geral, porque "Comissão Parlamentar Mista de Inquérito" contém "Comissão
Mista".

A abreviação oficial só é aceita **ancorada no início do nome**: a fonte escreve
ora "Comissão Parlamentar Mista de Inquérito - Fake News", ora "CPI da Pandemia",
e um nome que *começa* com "CPI " é inequívoco.

**Sigla solta nunca é usada.** É ali que mora a armadilha do ADR-034, onde `RQI`
parece "Requerimento de Informação" e é "Requerimento da Comissão de Serviços de
Infraestrutura".

A procedência viaja com o dado até a tela, em `origem_da_classe`:

| origem | vínculos | o que significa |
|---|---|---|
| `catalogo` | 5.743 | o tipo veio do `CodigoTipoColegiado` da fonte |
| `nome` | 1.268 | deduzido da forma oficial por extenso |
| `nenhuma` | 215 | não foi possível — **não entra na ficha** |

Os 215 que sobraram (3,0%) são cauda longa real: vetos e comissões temporárias
encerradas entre 1984 e 2013 cujo nome não diz o tipo — "CT - Reforma do Código
de Processo Civil", "CESP - Código Civil - 1984". Determiná-los exigiria ler a
sigla, que é exatamente o que esta decisão proíbe. **Ficam de fora.**

Cobertura em colegiado exibível: de 4.258 vínculos para **5.514**.

## O que a fonte não dá, e a tela diz

A rota do Senado devolve **três papéis**: Titular (4.708), Suplente (2.516) e
Nato (2). Zero Presidente, zero Vice, zero Relator. E **nenhum vínculo de Mesa
Diretora** — a Mesa não é "comissão" no modelo de dados do Senado.

O efeito é concreto: **Davi Alcolumbre preside o Senado, e a ficha dele mostra
apenas o Conselho de Ética.** A ficha de senador, por isso, não afirma quem
presidiu um colegiado — e diz na tela que não afirma, para que o silêncio não
seja lido como ausência do fato (Regra 5). Registrado como **L-30**.

## O que fica de fora do bloco

`frente` (796 vínculos) e `grupo_amizade` (701) não são promovidas a colegiado,
pelo mesmo motivo da Câmara: são adesão aberta, não assento. Continuam gravadas
em `stg_senado__comissoes`.

## Conferência (Regra 6)

Não há rota inversa na API — `composicao/comissao/CDH` e variantes respondem 153
caracteres — e a página pública carrega a composição por JavaScript, voltando
57 KB de casca. A conferência foi feita contra o **Regimento Interno do Senado**,
que fixa o número de cadeiras de cada comissão permanente:

| comissão | titulares no lake | Regimento |
|---|---|---|
| CCJ | 27 | 27 |
| CAE | 26 | 27 |
| CI | 21 | 23 |
| CAS | 20 | 21 |
| CRE | 18 | 19 |

A CCJ bate exatamente. As demais ficam **abaixo** do teto, nunca acima — cadeira
vaga existe, cadeira inventada não. Se a coleta duplicasse designações ou
arrastasse vínculo encerrado como vigente, o número passaria do teto regimental,
e não passa em nenhuma.

Confronto nominal: Paulo Paim aparece como titular da Comissão de Direitos
Humanos desde 18/02/2005, que é público e correto.

## Consequências

- 51 fichas de 2026 ganharam o bloco.
- A diferença de rigor entre Câmara e Senado deixou de ser uma omissão silenciosa
  e passou a ser uma ressalva escrita.
- O projeto ganhou um precedente: **quando duas telas usam a mesma fonte de
  identidade, elas não podem usar critérios diferentes sem que alguém explique
  por quê.** A L-28 sobreviveu meses porque ninguém comparou as duas.
- Abriu a L-30, que não está ao alcance do custo quase-zero do projeto.
