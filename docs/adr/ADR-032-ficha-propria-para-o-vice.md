# ADR-032 — Ficha própria para o vice de presidente e de governador

**Status:** Aceita · **Data:** 2026-09-01 · **Relacionada:** ADR-025 (chapa), ADR-018, F-21

## Contexto

O vice existia no site apenas como **cartão na ficha do titular**: nome, foto,
partido. Nada mais.

Isso é pouco para quem, em caso de vacância, **assume**. E deixava de fora
trajetória que já estava no lake: Geraldo Alckmin foi governador de São Paulo em
2003–2006, 2011–2014 e 2015–2018, e nenhum desses mandatos tinha onde aparecer.

São **216 candidaturas** em 2026 — 13 a vice-presidente e 203 a vice-governador —
todas com candidatura própria, foto de urna, bens declarados e trajetória
eleitoral já ingeridos.

## Decisão

Vice de presidente (cargo 2) e de governador (cargo 4) entram em `CARGOS`, o que
lhes dá — pelo mesmo caminho dos demais — ficha própria, página de listagem,
entrada na navegação, breadcrumb e sitemap.

**Suplente de senador (cargos 9 e 10) fica de fora.** São 665 candidaturas cuja
relação com o mandato é diferente: o suplente não compõe o Executivo nem assume
por vacância automática do mesmo modo. Ampliar para eles é decisão separada.

### O vínculo passa a valer nos dois sentidos

A ficha do titular já mostrava o vice; agora **linka** para ele. E a ficha do
vice ganhou o bloco **"Concorre na chapa de"**, com link de volta. Sem isso, a
ficha do vice seria a de alguém que aparece do nada — é a chapa que explica por
que aquela pessoa está na eleição.

O bloco diz também o que a tela não pode deixar implícito: **vice não recebe voto
próprio.** A chapa é votada como um par.

### Financiamento: o vice não promete um dado que nunca vem

O bloco vazio dizia *"prestação ainda não entregue — isto não significa campanha
sem arrecadação"*. Para um vice isso é falso por construção. Medido em
01/09/2026: os titulares tinham **55% a 85%** de cobertura na prestação de contas
e os **216 vices tinham zero**. A conta da chapa é apresentada pelo titular.

A ficha do vice passa a dizer isso, com link para a ficha onde os números estão.

## Dois defeitos que a mudança expôs

**O título da chapa vinha da contagem, não do cargo.** `"Vice" if len(chapa) == 1
else "Suplentes"` — e uma senadora com um único suplente encontrado (Mara Rocha,
AC) tinha a ficha chamando o suplente dela de "Vice da chapa". Agora o título vem
do cargo do titular.

**A mesma UF aparecia com duas grafias.** O TSE grafa sem acento nos anos
antigos: os blocos do Alckmin liam "SÃO PAULO · 2015–2018" e "SAO PAULO ·
2003–2006", como se fossem estados diferentes. São **11 UFs** com dupla grafia
em mandatos exibidos. O agrupamento e o rótulo passaram a usar a **sigla**, que é
estável, com o nome canônico vindo de `_UF_NOME`.

## Consequências

- O site vai de 739 para **952 páginas**. A publicação por FTP cresce na mesma
  proporção — cerca de 4 para 5 minutos, com as reconexões do ADR-027.
- A navegação passa de 6 para 8 itens.
- O bloco "Durante mandatos anteriores" aparece em **uma** ficha de vice
  (Alckmin). É pouco em número e muito em conteúdo: são três mandatos de governo
  de São Paulo que o site simplesmente não mostrava.
