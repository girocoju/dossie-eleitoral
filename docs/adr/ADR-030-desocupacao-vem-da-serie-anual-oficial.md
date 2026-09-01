# ADR-030 — A desocupação passa a vir da série anual oficial; o rendimento fica no "efetivamente recebido"

**Status:** Aceita · **Data:** 2026-09-01 · **Relacionada:** ADR-017 (L-22), ADR-029, Regra 6

## Contexto

A conferência dos 18 indicadores contra a fonte oficial ([VALIDACAO.md](../VALIDACAO.md))
encontrou duas divergências. Nenhuma era erro de extração; as duas eram escolhas
que produziam um número diferente do publicado.

### Desocupação

O valor anual era a **média simples dos quatro trimestres** da tabela 4099. O
IBGE calcula a taxa anual pela amostra anual agrupada, e os dois não coincidem:

| Ano | Média dos trimestres | IBGE publica |
|---|---|---|
| 2023 | 7,98% | 7,7% |
| 2024 | 6,85% | **6,6%** |

O problema não é o tamanho da diferença. É que **6,85% não existe em publicação
nenhuma do IBGE**. Quem conferisse encontraria 6,6% e concluiria que o site está
errado — e, num produto de consulta pública às vésperas de divulgação para
imprensa, essa conclusão custa mais do que a diferença de duas décimas.

A página de metodologia já avisava que "pode diferir da taxa anual que o IBGE
divulga". Avisar que o número diverge não é o mesmo que publicar o número certo.

### Rendimento do trabalho

A tabela 4566 / variável 5935 é o rendimento **efetivamente recebido**; o número
que sai nas manchetes é o **habitualmente recebido** — R$ 3.492 contra R$ 3.225
em 2024. As duas séries são oficiais e medem coisas diferentes: o habitual é o
que a pessoa costuma ganhar, o efetivo é o que entrou no mês de referência,
incluindo 13º, falta e atraso.

## Decisão

**A desocupação passa a vir da tabela 4562**, que é anual na origem (2012–2025),
tem Brasil e as 27 UFs, e devolve exatamente o número divulgado. Não há mais
agregação a fazer: o IBGE já publica o ano.

**O rendimento continua no "efetivamente recebido"**, e a tela passa a dizer que
é esse. A escolha é do dono do projeto; a obrigação que ela cria é de nomear a
série, não de trocá-la.

Também documentado, porque a unidade "R$ constantes" escondia: **a base de
deflação anda**. A série real é expressa a preços do período mais recente da
pesquisa, então o valor de um ano passado muda a cada divulgação — 2024 vale
R$ 3.492 na série que termina em 2025 e valia outro número antes. Não é revisão
do dado, é troca de base. A variação entre dois anos continua válida; o valor
absoluto não deve ser citado sem a data de extração.

## Consequências

- A série de desocupação muda em **todos** os anos e em todas as UFs. É mudança
  de número publicado, e por isso foi feita com autorização explícita.
- `media_anual` deixa de ter usuário no catálogo. A função continua, porque é
  maquinaria declarativa que o próximo indicador trimestral vai usar — mas os
  testes que a exercitavam passaram a montar um indicador sintético em vez de
  pegar `DESOCUPACAO` do catálogo. Teste de maquinaria não deve quebrar porque um
  indicador mudou de fonte.
- A página de metodologia ganhou a seção **Conferência com a fonte oficial**, que
  registra o que confere, os três casos em que dois números oficiais discordam
  entre si, o IDEB de 2021 que parece erro e não é, e o que **não** foi conferido.

## O que continua em aberto

O trio do SICONFI (`RECEITA_ESTADUAL`, `DESPESA_ESTADUAL`,
`RESULTADO_ORCAMENTARIO`) no nível Brasil é a soma dos 27 estados feita aqui, e
não existe consolidado publicado para comparar. Segue como pergunta no SPEC §11.
