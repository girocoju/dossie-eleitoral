# ADR-022 — Fonte indisponível não derruba a carga diária

**Status:** Aceita · **Data:** 2026-08-29 · **Feature:** F-10 (pipeline agendado)

## Contexto

Em 29/08/2026, tentando publicar o dossiê pela primeira vez, o pipeline caiu
duas vezes seguidas por motivo alheio ao projeto:

| Hora | O que caiu | Efeito |
|---|---|---|
| 02:28 | `apisidra.ibge.gov.br` — timeout | job inteiro morreu, **snapshot do TSE do dia perdido**, publicação bloqueada |
| 07:49 | `dadosabertos.camara.leg.br` — timeout | idem |

Nos dois casos a fonte voltou sozinha em minutos. Nos dois casos o custo foi
desproporcional: uma instabilidade de API pública decidiu que o dossiê não
sairia do ar, e — pior — que o snapshot diário do TSE não seria tirado.

O snapshot é o que não volta. O TSE publica apenas o **estado atual**, sem
histórico: a série de alterações de candidatura é construída tirando uma foto por
dia, e um dia sem foto é um buraco permanente.

## O problema com a solução óbvia

A primeira correção foi tornar as fontes anuais tolerantes a falha — um laço com
`if ... else warning`. Funcionou para o SIDRA e falhou como princípio: qualquer
erro virava aviso.

Isso troca um modo de falha ruim por outro pior. Se o TSE mudar o endereço de um
pacote, a resposta é **404**, o script falha, o aviso é emitido, o job fica verde
— e a série para de atualizar em silêncio, com o site mostrando dado velho como
se fosse novo. É a mesma família de erro do orçamento federal (L-22 / ADR-017):
tudo verde, número errado na tela.

`|| true` no YAML não sabe a diferença. Nada no YAML sabe.

## Decisão

A classificação é feita **pela causa da exceção**, em `ingest/common/cli.py`, e o
processo comunica a decisão pelo código de saída:

| Código | Significado | O que o workflow faz |
|---|---|---|
| `0` | carregou | segue |
| `75` | falha **transitória** de rede (`EX_TEMPFAIL`) | `::warning::` + linha no resumo, e segue |
| outro | erro de verdade | **derruba o job** |

`DownloadError` passa a carregar a causa e a expor `transitoria`:

```
timeout, conexão recusada, 408, 425, 429, 500, 502, 503, 504   → transitória
404, 403, 410, 401, 400                                        → NÃO
sem causa conhecida                                            → NÃO
```

`HTTPError` é subclasse de `URLError`, então a ordem dos `isinstance` importa:
invertida, todo 404 viraria transitório e a distinção inteira se perderia. Há
teste para isso.

Na dúvida, **para**. Um job vermelho custa uma re-execução; um job verde com dado
velho custa a confiança no número que está na tela.

## O TSE continua fatal

A carga do TSE não passa pelo tradutor: ela derruba o job mesmo em falha de rede.

Parece inconsistente e não é. Para todas as outras fontes, "não atualizou hoje"
significa que o dado de ontem continua valendo e amanhã atualiza. Para o TSE,
significa um buraco permanente na série de alterações. O vermelho é o que dá
chance de re-executar dentro do dia — e é exatamente o que se quer.

## Consequências

**O que fica visível.** Cada fonte que não atualizou emite um `::warning::` com
título próprio e escreve uma linha no resumo do job. Não é silêncio: é a
diferença entre *"o SIDRA não respondeu hoje"* e *"o pipeline quebrou"*.

**Nenhum dado é inventado.** O valor anterior permanece no BigQuery com o
`_extracted_at` anterior — que é o que a ficha já mostra ao leitor, como toda
tela do projeto (Constituição §0.3).

**Uma carga parcial ainda constrói os marts.** `dbt build` roda sobre o que está
no BigQuery, e continua **fatal**: teste de dado que falha é sempre erro, nunca
instabilidade.

**Doze módulos mudaram junto**, todos da mesma forma — `main()` passa por
`executar()`. A uniformidade é o ponto: qualquer script de ingestão novo herda o
comportamento sem que ninguém precise lembrar.

## Alternativa descartada

**Retry no nível do passo.** Ajudaria, e `get_json` já tenta 3 vezes com backoff
antes de desistir — o timeout do SIDRA sobreviveu a isso. Mais tentativas só
adiam a decisão sem responder a pergunta que importa: *esta falha deve parar o
pipeline?* A classificação responde; o retry, não.
