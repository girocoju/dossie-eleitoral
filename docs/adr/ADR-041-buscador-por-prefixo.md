# ADR-041 — Buscador na home, com um arquivo por prefixo

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** F-23, F-18/ADR-040, Constituição §0.1, Regra 5

## Contexto

A F-18 deu ficha própria a 20.162 candidaturas. Chegar a uma delas, porém, exigia
saber o cargo **e** o estado: escolher "Deputado Estadual", escolher "SP", e então
filtrar entre 1.126 nomes. Quem lê um nome no jornal não sabe nem o cargo nem a
UF — sabe o nome.

## Decisão

Campo de busca na home, sobre todas as fichas, por nome ou número na urna.

### Um arquivo por prefixo de duas letras

Um índice único com 20.162 nomes daria ~1,5 MB (e ~10 MB com os nomes completos).
Numa home aberta no celular em rede fraca, isso é meio minuto antes de a primeira
letra valer alguma coisa — o mesmo problema que já quebrou a listagem de deputado
estadual, resolvido ali por UF (ADR-018).

O índice é quebrado por prefixo de duas letras do termo buscado. O navegador
baixa **um** arquivo. Medido:

| | |
|---|---|
| arquivos | 409 |
| índice inteiro em disco | 9,9 MB |
| maior arquivo (`ma`) | 417 kB — **136 kB comprimido** |
| home | 12 kB (era 5,3 kB) |

O servidor entrega JSON com Brotli (medido: 536 kB → 56 kB), então o pior caso no
fio é da ordem de 100 kB, menos que a listagem por UF que o projeto já aceita.

Duas letras e não três: com uma, `m` juntaria Marcos, Maria, Miguel e Moacir num
arquivo só; com três, seriam 2.604 arquivos e o maior continuaria grande — `sil`
sozinho tem 3.322 pessoas, porque Silva é Silva.

### O nome completo entra no índice

Nome de urna é apelido curto: "ZULU", "DR. TARCÍSIO", "PROFESSORA ANA". Medido
sobre as 20.838 candidaturas exibidas:

| termo | no nome de urna | no nome completo |
|---|---|---|
| SILVA | 301 | **3.322** |
| JOSE | 83 | **335** |

Indexar só o nome de urna perderia nove em cada dez pessoas que alguém procuraria
pelo sobrenome. Antes da correção, `jose da silva` devolvia **zero**; depois,
devolve 134. `tarcisio de freitas` devolve o Governador de São Paulo, cujo nome de
urna é apenas "TARCÍSIO".

O nome completo viaja **na linha**, não apenas nos termos. Se ele apenas colocasse
a linha no arquivo sem estar nela, o navegador acharia a pessoa pelo índice e a
descartaria no filtro — "nada encontrado" para quem está na base.

## O que impede a busca de mentir

Um `fetch` que volta 404 é indistinguível de "não há ninguém com esse nome": a
tela diria *"nada encontrado"* nos dois casos. Isso é **ausência virando
afirmação**, exatamente o que a Regra 5 proíbe.

Por isso a home carrega a lista dos 409 prefixos que existem. Prefixo fora dela é
**certeza** de que não há ninguém; prefixo dentro dela que não carrega obriga a
tela a dizer *"não foi possível carregar a busca agora"*. Custa poucos kB e
resolve a ambiguidade na origem.

Pelo mesmo motivo, `normalizar()` no gerador e o `normalize("NFD")` do navegador
têm um teste que confere a equivalência em vez de assumi-la: se divergissem, o
navegador pediria um arquivo inexistente e diria "nada encontrado" para um nome
que está lá.

## Não é ranking

A ordem é: quem **começa** pelo texto digitado antes de quem apenas o contém,
depois alfabética. É relevância de digitação. Nada na tela ordena candidato por
qualquer coisa que ele tenha feito (Constituição §0.1).
