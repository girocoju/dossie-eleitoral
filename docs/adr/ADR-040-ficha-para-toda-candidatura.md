# ADR-040 — Ficha própria para toda candidatura

**Status:** Aceita · **Data:** 2026-09-03 · **Relacionada:** F-18, Constituição §0, SPEC §2.2, ADR-038, ADR-039

## Contexto

Até 03/09/2026 só os 529 cargos majoritários tinham página própria. As 19.418
candidaturas proporcionais tinham listagem filtrável e mais nada.

O argumento contra a mudança está registrado no próprio gerador desde a F-07, e
não era ruim: 19 mil páginas com poucos campos distintos são o que buscador
classifica como conteúdo raso, e o risco não é penalidade — é o site inteiro
passar a ser lido como de baixa qualidade.

Ele perde por um critério que não é ranqueamento: **utilidade pública**
(Constituição §0). Quem decide o voto para deputado enfrenta 1.126 nomes só em
São Paulo, e é aí que uma ficha ajuda **mais**, não menos. Ficha sem endereço
próprio não é compartilhável, e um site de consulta serve quem chega por link.

Foi também a falta mais citada por quem usou o site.

## Decisão

Uma página por candidatura, no mesmo formato e pelo **mesmo caminho de código**
das majoritárias: `carregar_fichas(cliente, cargos)` passa a receber os oito
cargos. Duas rotinas de carga divergiriam com o tempo, e a divergência apareceria
como ficha de deputado com menos rigor que a de senador — o contrário do que a
F-18 argumenta.

### O que a ficha do deputado tem, e o que não tem

Tem foto de urna, perfil declarado, legenda completa, número na urna, trajetória
eleitoral, prestação de contas e — para quem já teve mandato — atividade
legislativa e plenário.

**Não** tem indicador socioeconômico atribuído ao mandato de deputado.
`fct_mandato_indicador` só tem linha para mandato **executivo**, então o bloco só
aparece para quem já foi Presidente ou Governador — e fala do *período* daquele
mandato, exatamente como na ficha de governador. Nenhum número regional é ligado
a um mandato parlamentar (SPEC §2.2).

A nota sobre plano de governo passa a nomear o cargo da ficha. Ela dizia
"Senador é majoritário, mas não consta da lista" em toda ficha sem plano — numa
ficha de deputado, isso convida à leitura de que o candidato deixou de entregar
algo.

## O que a escala obrigou a mudar

**O CSS saiu de dentro da página.** Embutido, custava 9,1 kB em cada uma das 744
páginas — 6,8 MB, aceitável. Em 19.947 páginas seriam **180 MB da mesma folha
copiada**, mais da metade do site. Como arquivo, o navegador baixa uma vez e
reaproveita; o custo é uma requisição a mais na primeira página. O endereço leva
a impressão digital do conteúdo (`dossie.css?v=488cf59c`), sem a qual o pior caso
do cache é HTML novo com CSS velho — layout quebrado sem erro visível.

**O sitemap virou índice.** `/sitemap.xml` continua sendo o único endereço que
alguém precisa conhecer, mas passa a listar sitemaps por cargo e UF em
`/sitemaps/`. Vinte mil URLs cabem no limite formal de 50 mil; arquivos menores
são rastreados com mais frequência, e a mudança de um estado deixa de obrigar o
robô a reprocessar os outros vinte e seis.

**O filtro `in (...)` das consultas deixou de compensar.** Com 529 fichas, listar
os `id_pessoa` evitava ler tabelas inteiras. Com 19.947, a lista cobre quase toda
a base de 2026: o SQL passaria de 700 kB — perto do teto de 1 MB do BigQuery — e
filtraria quase nada. Acima de 4.000 chaves a consulta vem inteira e o recorte
acontece no `por_pessoa.get()` que já existia em toda função.

**O link da listagem vem pronto do gerador.** O caminho da ficha é
`slug(nome_urna)-sq`, e `slug()` normaliza acento em NFD descartando o que não é
ASCII. Reimplementar isso em JavaScript daria endereço diferente para "JOSÉ" em
algum navegador — 19 mil links quebrados. O JSON de cada estado passa a trazer o
slug já calculado.

## Números medidos

| | antes | depois |
|---|---|---|
| páginas HTML | 955 | ~20.400 |
| tamanho de uma ficha | 19,4 kB | ~7 kB (sem o CSS embutido) |
| site inteiro | 48,8 MB | ~150 MB |
| arquivos enviados por dia | 1.013 | ~5% deles (ADR-038 + ADR-039) |

## Consequências

- A publicação inicial é longa — é uma vez. Depois dela o envio é incremental.
- `--sem-proporcionais` existe para iterar no visual. Publicar uma saída assim é
  recusado pela limpeza de órfãs (ADR-037), que não distingue isso de geração
  truncada — e é exatamente o comportamento certo.
