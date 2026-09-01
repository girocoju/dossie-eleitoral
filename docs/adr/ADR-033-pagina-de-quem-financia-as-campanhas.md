# ADR-033 — Página de quem financia as campanhas

**Status:** Aceita · **Data:** 2026-09-01 · **Relacionada:** ADR-020 (CPF do doador fora), Constituição §0.1 e §0.7

## Contexto

O financiamento de campanha só existia **dentro de cada ficha**: os 20 maiores
doadores daquela candidatura. Para responder "quem financia esta eleição" era
preciso abrir 745 fichas e somar à mão.

O lake tem **23.532 repasses declarados**, de **15.197 financiadores**, somando
**R$ 2,6 bilhões** na eleição de 2026.

## A decisão que precisou ser tomada antes de construir

Uma tabela global muda a **exposição de pessoa física**, não só a comodidade.

Medido em 01/09/2026: o site publicava **704** pessoas físicas (os 20 maiores de
cada ficha majoritária). Uma tabela com todos publicaria **14.958** — ou seja,
**14.254 cidadãos privados** que não apareciam, cada um pesquisável por nome ao
lado do candidato que apoiou. Doação de campanha revela convicção política.

O dado é público por lei e o TSE o divulga. A decisão foi levada ao dono do
projeto com os números na mão, e ele escolheu **publicar todos, sem limiar** — e
manter o autofinanciamento no ranking, marcado.

Fica registrado que a alternativa considerada era publicar só pessoa jurídica
(239 financiadores, 94% do dinheiro, zero exposição nova de indivíduo) ou aplicar
um limiar de valor.

## Decisão

Página `/doadores/`, uma linha por **financiador × candidatura**.

**Quem financia mais de um candidato aparece uma vez para cada, com o valor de
cada.** Somar apagaria justamente a distribuição do apoio — que é a informação
que a tabela existe para mostrar. Cada linha carrega também quantas candidaturas
aquele financiador banca, o número que transforma a tabela em leitura: um
financiador com 1 é apoio; o Partido Liberal, com **1.023**, é outra coisa.

### Isto não é ranking de político

A Constituição §0.1 proíbe ranking de "melhor/pior político". Uma tabela de
quanto cada financiador repassou a cada candidatura, ordenada por valor, não
emite juízo sobre candidato nenhum. Nenhuma coluna qualifica quem recebeu.

### Sem CPF, com CNPJ

CPF de pessoa física nunca foi ingerido (ADR-020): o TSE publica em texto puro, e
o nome basta para prestar contas. CNPJ de empresa entra, porque identifica quem
financia e é de pessoa jurídica.

### Autofinanciamento entra, marcado

São 2.450 linhas em que o financiador é o próprio candidato. Ficam no ranking,
por decisão do dono do projeto, com marca **próprio** — dinheiro próprio e apoio
externo são coisas diferentes, e a tela distingue sem nota de rodapé.

## Como a página aguenta 23 mil linhas

O JSON sai como **array de arrays**, não de objetos: repetir catorze nomes de
chave em 23.532 linhas triplicaria o download. A página desenha **200 linhas por
vez** — jogar 23 mil `<tr>` no DOM trava o celular, que é a maior parte do acesso
(ADR-018).

O campo `ramo` do financiador traz "Atividades de organizações políticas" em
**7.390 das 8.082** linhas de pessoa jurídica, respondendo por 99,6% do dinheiro
jurídico. Essa string não viaja no payload — o nome "PARTIDO LIBERAL (PL)" já diz
o mesmo, e omiti-la economiza cerca de 300 KB. Os **outros** ramos vão inteiros:
são justamente os casos que informam.

## Um fato que a tabela deixa evidente

**99,6% do dinheiro de pessoa jurídica vem de diretório partidário ou do fundo
eleitoral**, não de empresa. Não é acaso: doação de empresa a candidato é
inconstitucional desde 2015 (ADI 4650). A página diz isso, porque sem a frase o
leitor conclui o contrário ao ver "pessoa jurídica" no topo da tabela.
