# ADR-013 — Proposta de governo: registrar a existência e apontar para a fonte

**Status:** Aceita · **Data:** 2026-08-28 · **Feature:** F-14

## Contexto

A página principal precisa mostrar, por candidato, se ele apresentou proposta de
governo. A proposta é exigida pela **Lei 9.504/97, art. 11, §1º, IX** — que cita
"propostas defendidas pelo candidato a Prefeito, a Governador de Estado ou do
Distrito Federal e a Presidente da República". Em 2026 isso são **211 de 20.769
candidaturas (1,0%)**: 13 a Presidente e 198 a Governador.

A sondagem de 28/08/2026 estabeleceu:

- **Não existe pacote em lote.** Quatro caminhos plausíveis no portal de dados
  abertos retornam 404, inclusive para 2022 (ver `docs/LACUNAS.md`, L-17).
- **A API do DivulgaCandContas responde**, com o mesmo conjunto de cabeçalhos de
  navegador que o CDN exige (L-18):
  `/divulga/rest/v1/candidatura/buscar/2026/{UE}/20322002026/candidato/{sq_candidato}`
- O campo `arquivos` traz os documentos do candidato, e a proposta de governo é a
  que tem **`codTipo = 5`**. Os demais são certidões judiciais (TRF, TJ), que o
  projeto não usa.
- **O download do PDF não é acessível por URL documentada.** O campo `url` traz
  apenas um prefixo de caminho, e nenhum padrão de download testado responde.

## Decisão

Registrar a **existência** da proposta e **apontar para a página oficial** do
candidato. Não baixar nem re-hospedar os PDFs.

Para cada candidatura majoritária de 2026, `fct_candidatura` passa a ter:

| Coluna | O que é |
|---|---|
| `proposta_obrigatoria` | TRUE para cargos 1, 3 e 5 — é a lei, não o dado |
| `tem_proposta_governo` | TRUE quando há arquivo `codTipo = 5` |
| `n_arquivos_proposta` | quantos documentos de proposta foram anexados |
| `nome_arquivo_proposta` | nome do arquivo, como o candidato enviou |
| `url_proposta_oficial` | link para a página do candidato no DivulgaCandContas |

## Motivo

**Por que não re-hospedar.** Três razões, em ordem de peso:

1. **Credibilidade.** Num produto cuja tese é "dados públicos, com fonte e data",
   mandar o leitor à fonte oficial vale mais que servir uma cópia nossa. Ele
   confere no TSE, não em nós.
2. **A cópia envelhece.** O candidato pode substituir a proposta até o registro
   final. Um link acompanha; um PDF baixado em agosto não.
3. **Postura.** Baixar em lote exigiria engenharia reversa de um endpoint não
   documentado de um sistema de consulta. É diferente de consumir pacotes que o
   TSE publica justamente para download em massa. Fazê-lo seria uma decisão do
   dono do projeto, não uma escolha técnica minha — e ele optou por não fazer.

**Por que ainda assim consultar a API.** Sem consultar, só daria para dizer
"este cargo exige proposta" — uma afirmação sobre a lei, não sobre o candidato.
Com a consulta, a tela distingue três estados honestos: *não se aplica*,
*apresentou* e *não consta*. Essa distinção é o conteúdo do disclaimer.

## Volume e ritmo

529 candidaturas, uma requisição cada, com pausa de 2 s — cerca de 18 minutos numa
execução completa. Para o pipeline diário não pagar isso todo dia, a ingestão só
reconsulta registros com mais de 7 dias (`--max-idade-dias`); nos demais dias ela
faz zero requisições.

## Consequência

- A tela nunca mostra o texto da proposta, só o link. Se um dia o produto quiser
  analisar o conteúdo, é outra feature e outra decisão.
- Se o TSE mudar a rota do DivulgaCandContas, os links quebram. O teste de
  cobertura não pega isso — link quebrado não é testável sem seguir o link, o que
  o projeto não faz. Fica registrado como risco conhecido.
- `codTipo = 5` é um código não documentado, inferido da observação. Se ele mudar
  de significado, `tem_proposta_governo` fica errado. O teste de sanidade cobre o
  caso grosseiro (cobertura despencar), não o sutil.

## Correção após a medição — 2026-08-28

A primeira versão desta decisão incluía **Senador** entre os cargos obrigados, por
ele ser majoritário. A consulta às 529 candidaturas majoritárias desmentiu:

| Cargo | Com proposta | |
|---|---:|---:|
| Presidente | 13 de 13 | 100,0% |
| Governador | 193 de 198 | 97,5% |
| **Senador** | **0 de 318** | **0,0%** |

O zero absoluto do Senado não é omissão de 318 pessoas — é que a lei não pede.
Senador é majoritário, mas não consta do art. 11, §1º, IX.

Se `proposta_obrigatoria` tivesse ido para produção como estava, a tela exibiria
"não consta proposta no TSE" para todos os 318 candidatos ao Senado. Num produto
que se declara apartidário e descritivo, imputar a 318 pessoas uma omissão que a
lei nunca exigiu delas seria o pior tipo de erro possível — não um número errado,
mas uma acusação.

**Corrigido:** `proposta_obrigatoria` é TRUE apenas para os cargos 1 e 3. As linhas
de Senador permanecem em `raw_tse.propostas` como evidência da medição, e são
filtradas no staging.

Os **5 governadores sem proposta** (2,5%) são achado real e aparecem como
"não consta" — para eles a lei exige, e a fonte não registra.
