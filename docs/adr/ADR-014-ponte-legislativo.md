# ADR-014 — Ponte de identidade entre TSE e Câmara/Senado

**Status:** Aceita · **Data:** 2026-08-28 · **Feature:** F-15

## Contexto

93% das candidaturas de 2026 são para cargos legislativos, e hoje essas fichas têm
apenas perfil declarado e trajetória eleitoral. Falta o que a pessoa **fez** no
mandato — e essa é a única prestação de contas defensável para um parlamentar,
já que o vínculo entre um deputado e um indicador socioeconômico regional é fraco
demais para ser mostrado (SPEC §2.2).

O risco que eu havia apontado como maior era o **casamento de pessoa**: a suposição
de que Câmara e Senado não publicariam CPF, obrigando a casar por nome — o mesmo
fallback que o projeto marca como `link_confiavel = false`.

A sondagem de 28/08/2026 desmentiu metade disso.

## O que a medição mostrou

| Casa | Chave disponível | Resultado |
|---|---|---|
| **Câmara** | **CPF** em `/deputados/{id}` | **20 de 20** casaram por `cpf_hash` na amostra |
| **Senado** | nome completo + data de nascimento (sem CPF) | **81 de 81** casaram por nome completo |

Os dois únicos nomes de senador ambíguos na base foram investigados:

- **Francisco de Assis Rodrigues** — três pessoas distintas (RN, RR, SP), cada uma
  com data de nascimento diferente. Nome + nascimento desambigua.
- **José da Cruz Marinho** — uma pessoa só. O registro de 1998 não tem CPF e caiu
  no fallback do próprio projeto, ganhando `id_pessoa` diferente. É a lacuna L-10
  se manifestando, não homonímia.

Ou seja: **zero ambiguidade real** entre os 81 senadores em exercício.

## Decisão

1. **Câmara casa por `cpf_hash`**, exatamente como o projeto já liga eleições entre
   si (ADR-005). `metodo_casamento = 'cpf'`, `casamento_confiavel = true`.
2. **Senado casa por nome completo normalizado + data de nascimento.**
   `metodo_casamento = 'nome_nascimento'`, `casamento_confiavel = false`.
3. A distinção **viaja com o dado**, não fica num comentário. Qualquer tela que
   mostre atividade parlamentar de um senador carrega a marca de que a identidade
   foi inferida, não confirmada.
4. Um parlamentar que não case fica **de fora**, e a contagem de não casados é
   registrada. Nunca se atribui atividade a quem não se tem certeza de ser.

## O que esta feature NÃO faz

Registrado aqui porque é a parte que mais pode dar errado depois:

- **Nenhum ranking de parlamentar.** "Compareceu a 87% das sessões" vira placar com
  facilidade, e placar é o que a Constituição §1 proíbe. Toda medida de atividade
  entra com comparador — a média da bancada, do partido, da Casa — do mesmo jeito
  que os indicadores socioeconômicos entram com a linha do Brasil.
- **Nenhum juízo sobre o conteúdo de voto.** O projeto não classifica proposição
  como boa ou ruim, nem voto como certo ou errado.
- **Nenhuma inferência de alinhamento** a partir de padrão de votação. Agrupar
  parlamentares por semelhança de voto produz rótulos que a fonte não dá.

## Consequência

- Uma casa nova de dados (`raw_legislativo`) e duas APIs a manter, com modelos
  diferentes: a Câmara é REST/JSON limpo, o Senado é JSON derivado de XML e
  aninhado.
- O Senado depende de casamento por nome. Se um senador mudar de nome civil, o elo
  quebra — e quebra em silêncio, virando "senador sem atividade". O teste de
  cobertura (81 esperados) é o que acusa.
- A atividade parlamentar em si (votações, presença, proposições) é fase seguinte.
  Esta decisão entrega a **ponte**, que é o que tudo depende, e a fixa antes de
  qualquer métrica ser construída sobre ela.
