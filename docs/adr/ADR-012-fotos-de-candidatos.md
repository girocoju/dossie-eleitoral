# ADR-012 — Fotos em bucket público, não no BigQuery

**Status:** Aceita · **Data:** 2026-08-27 · **Feature:** F-13 (implementada)

## Contexto

A página principal do produto é a lista de candidatos com filtro por cargo. Sem
foto ela é uma tabela; com foto é um raio-X. O TSE publica a foto oficial de urna
de cada candidato, e a conferência do arquivo real (27/08/2026, pacote do Acre)
mostrou que a fonte é boa:

| | |
|---|---|
| Nomenclatura | `F{SG_UE}{SQ_CANDIDATO}_div.jpg` |
| Junção com o mart | os componentes do nome são os da `sk_candidatura` |
| Cobertura medida | 385 de 387 candidaturas do AC — **99,5%**, zero fotos órfãs |
| Tamanho | mediana **5 KB**, 161×225 px |
| Volume estimado (2026) | **100–250 MB** |

## Decisão

1. As imagens vão para um bucket **público** do Cloud Storage
   (`radar-brasil-fotos`, região `US`, *uniform bucket-level access*).
2. O BigQuery guarda **apenas a URL**, em `dim_candidato.url_foto`.
3. Escopo: **somente 2026**.

## Motivo

**Por que não no BigQuery.** Binário não pertence a um warehouse analítico.
Guardar 250 MB de JPEG em BYTES infla o storage, não é consultável, e o Power BI
em Import mode carregaria as imagens para dentro do modelo — o que engorda o
`.pbix` publicado e torna o refresh lento. Com URL, o navegador do visitante busca
só as fotos que a tela mostra.

**Por que público.** O relatório será publicado com *Publish to web*, sem
autenticação. Uma imagem protegida simplesmente não apareceria. O bucket serve
exatamente o que o TSE já publica abertamente.

**Por que só 2026.** O pacote de 2022 do AC sozinho tem 14,7 MB — sete eleições
multiplicariam o armazenamento por um ganho que a página principal não usa. Se um
dia a ficha histórica precisar, entra como feature própria.

## Privacidade

A Constituição §7 proíbe expor CPF e endereço. A foto de urna é diferente em
natureza: é o retrato que o TSE publica **para que o eleitor reconheça o candidato
na urna**. Republicá-la num painel eleitoral é o uso para o qual ela existe.

Ainda assim, três limites:

- **Só candidatos.** Nenhuma foto de terceiros, nem de eleitores.
- **Só o ano em disputa.** Fotos não viram acervo histórico de pessoas.
- **Sem tratamento.** Nenhum reconhecimento facial, nenhuma inferência de
  característica a partir da imagem, nenhum cruzamento biométrico. A foto é
  ilustração da ficha, não fonte de dado.

Candidatura indeferida ou renunciada mantém a foto: ela faz parte do registro
público daquela candidatura, e a ficha mostra a situação ao lado.

## Custo

Dentro do *Always Free* do Cloud Storage (5 GB em região dos EUA). O tráfego é
desprezível: a 5 KB por foto, os 100 GB gratuitos de saída mensal comportam 20
milhões de exibições. As operações de leitura têm franquia de 50 mil/mês e, acima
disso, custam US$ 0,004 por 10 mil — centavos.

## Consequência

- Mais um recurso de infraestrutura para versionar e recriar: o bucket precisa
  entrar no `make bootstrap` para a Constituição §4 continuar valendo.
- A URL vira contrato público. Mudar o caminho quebra relatório publicado, então o
  caminho é determinístico e estável: `gs://radar-brasil-fotos/2026/{SG_UE}/{sq_candidato}.jpg`.
- Se o TSE mudar a nomenclatura, o teste de cobertura ≥ 95% falha a carga — o
  mesmo princípio que já protege os layouts (ADR-008).

## Resultado da implementação — 2026-08-28

| | |
|---|---|
| Fotos no bucket | **20.765**, das 28 unidades eleitorais |
| Cobertura em `dim_candidato` | **99,98%** (20.765 de 20.769 candidaturas de 2026) |
| Caminho | `gs://radar-brasil-fotos/2026/{SG_UE}/{sq_candidato}.jpg` |
| URL pública | responde `200 image/jpeg`, sem autenticação, `Cache-Control: public, max-age=86400` |
| `dbt build` | 147 de 147 |

O upload pula o que já está no bucket: a execução diária custa uma listagem por
unidade eleitoral e envia só foto de candidatura nova ou substituída.
