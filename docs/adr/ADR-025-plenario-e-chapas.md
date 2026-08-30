# ADR-025 — Votos, presença e a chapa

**Status:** Aceita · **Data:** 2026-08-30 · **Features:** F-20, F-21 · **Estende:** ADR-024

## Contexto

Três pedidos do usuário, e cada um encontrou uma resposta diferente na fonte.

## 1. Votações — feito, agregado

A Câmara publica `votacoesVotos-{ano}.csv` desde 2003: como cada deputado votou,
voto a voto. Um ano passa de 50 MB; 2003-2026 seriam **dezenas de milhões de
linhas**.

**Agregado na ingestão**, por (deputado, ano): quantas votações e a distribuição
entre sim, não, abstenção, obstrução. A tabela fica em **13 mil linhas** em vez de
milhões, e o custo perto de zero (Constituição §0.5) — a mesma decisão já tomada
para a votação do TSE.

**O que se perde:** não dá para perguntar *"como fulano votou na PEC tal"*. Se essa
pergunta entrar no escopo, a fonte continua lá.

**O que não se faz com o número.** A distribuição está na ficha porque é registro
público. O que o projeto **não** faz é interpretá-la: um voto só significa algo
junto com o que estava em votação, e classificar isso seria editorializar (§0.1).

## 2. Presença — feito, e o pedido é que destravou

Eu havia recomendado **não** fazer, e o usuário reformulou: *"não necessariamente
a % de presença, mas só o volume tá ótimo"*.

A reformulação resolve o impasse, e vale explicitar por quê. `eventosPresencaDeputados`
diz em que eventos o deputado esteve. **Não diz a quantos ele devia ter
comparecido** — e sem denominador não existe percentual. Derivar um exigiria
decidir o que conta como ausência, onde falta se confunde com comissão paralela,
missão oficial e licença médica.

**Volume é fato verificável; taxa é inferência.** Um *"62% de presença"* errado é
uma acusação publicada sobre uma pessoa real. A frequência oficial existe no
portal da Câmara, fora do dado aberto: o caminho honesto seria citá-la, nunca
inferi-la.

**Plenário separado de comissão**, porque são trabalhos diferentes e somá-los num
número só esconderia isso. Medido: 2,5 milhões de presenças, 1,5 milhão em
plenário.

A tela diz, junto do número, que ele não é taxa.

## 3. Chapa — o que faltava não era o vice

Vice e suplente **já estavam no lake**, com candidatura própria, foto e perfil:
13 vice-presidentes, 203 vice-governadores e 661 suplentes de senador em 2026.

O que não existe em lugar nenhum do pacote em lote é a **chapa**. Geraldo Alckmin
estava na base como candidato a Vice-Presidente pelo PSB, e nada dizia que ele
concorre com Lula.

O vínculo só aparece no DivulgaCandContas, no campo `vices` do detalhe — uma
consulta por chapa, 529 em 2026, cerca de onze minutos.

**Não copiamos os dados do vice.** `dim_chapa` guarda o par e o cargo; nome,
partido e foto vêm de `dim_candidato`, onde já estão. Duplicar criaria uma
segunda versão da verdade, que envelheceria sozinha enquanto o TSE ainda aceita
alteração de cadastro.

### O vínculo foi verificado contra a outra ponta

Um vice ligado ao titular errado não quebra página: produz uma **afirmação falsa
sobre duas pessoas ao mesmo tempo**. A junção usa `sq_candidato`, que é
inequívoco, e `assert_chapa_aponta_para_a_pessoa_certa` confere o resultado contra
o nome que o pacote em lote traz para o mesmo `sq_candidato`.

Resultado: **889 vínculos, 887 resolvidos, zero com primeiro nome divergente**.

As cinco divergências de nome são cosméticas e estão anotadas no teste — apóstrofo
que o pacote em lote remove (`D'AVILA` → `D AVILA`), abreviação (`PROFª` → `PROF.`)
e um nome de urna alterado entre as duas fontes.

Os dois não resolvidos são suplentes registrados depois da última publicação em
lote (L-23), e aparecem como ausentes em vez de virarem linha vazia.

## Consequência de engenharia

Os anos históricos de votos e presença são **carga separada**, como as
legislaturas da ADR-024: ano encerrado não muda, e `load_intervalo` substitui
apenas a partição daquele ano. O pipeline diário carrega 2025-2026 e não encosta
em 2003-2024.

As chapas rodam **diariamente**, e essa é a exceção: o TSE aceita substituição de
vice até a eleição, então o vínculo de ontem pode não valer hoje.

## O que a ficha mostra agora

Por legislatura, junto das proposições que já existiam: **votações em que votou**,
**sessões de plenário**, **eventos no total** e a distribuição dos votos. E, para
candidatura majoritária, o bloco **Vice** ou **Suplentes** da chapa, com foto.

Cargo proporcional não tem chapa — deputado concorre sozinho —, então o bloco não
existe nessas fichas, em vez de aparecer vazio.
