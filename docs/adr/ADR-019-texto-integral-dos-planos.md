# ADR-019 — Texto integral dos planos de governo

**Status:** Aceita · **Data:** 2026-08-28 · **Emenda a:** ADR-013 · **Feature:** F-14b (S19)

## Contexto

A [ADR-013](ADR-013-proposta-de-governo.md) decidiu publicar **existência + link**,
sem re-hospedar o PDF. Dois motivos sustentavam aquilo:

1. o download exigiria engenharia reversa da aplicação do TSE;
2. uma cópia envelhece, e a fonte oficial é mais confiável.

O primeiro caiu. O segundo mudou de peso.

### O que derrubou o motivo 1

A ADR-013 concluiu que o PDF era inalcançável porque o caminho de arquivo que a
API devolve responde **403**:

```
candidaturas/oficial/2026/BR/BR/6257/candidatos/21107/PLANO DE GOVERNO.pdf   → 403
```

Estava certo sobre o 403 e errado sobre a conclusão. **O app do TSE não usa esse
caminho.** Ele usa um endpoint REST, encontrado em 28/08/2026 lendo o chunk `829`
do bundle Angular de `divulgacandcontas`:

```
/divulga/rest/arquivo/doc/{idArquivo}   → 200 application/pdf
```

Não houve engenharia reversa: o endereço está no JavaScript público da aplicação.

### O que mudou o peso do motivo 2

O link parou de funcionar. A rota de SPA que a ADR-013 registrou
(`/divulga/#/candidato/...`) devolve **"ERRO AO CARREGAR A PÁGINA"** na versão
2.8.17 do app do TSE. Um "link para a fonte oficial" que leva a uma tela de erro
não é mais confiável que uma cópia — é menos.

### O que a medição mostrou

Amostra de 18 planos, em duas rodadas:

| | |
|---|---|
| Downloads bem-sucedidos | **18 de 18** |
| Renderam texto | **17** |
| Sem camada de texto (escaneado) | **1** |
| Mediana | **111 mil caracteres** (~60 páginas) |
| Maior | 305 mil caracteres, 200 páginas |

## Decisão

O texto integral passa a ser ingerido e publicado, em tabela própria
(`raw_tse.planos`), por um módulo próprio (`ingest/planos.py`).

**Módulo separado de `propostas.py` de propósito.** São perguntas diferentes com
riscos diferentes:

| | pergunta | risco se errar |
|---|---|---|
| `propostas.py` | o plano existe? | acusar alguém de omissão |
| `planos.py` | o que ele diz? | **deturpar a proposta de alguém** |

### O que nunca é feito

**Resumo.** Resumir é escolher o que importa no programa de alguém — é
editorializar, e a Constituição §0.1 proíbe. O texto vai inteiro ou não vai.
Foi a primeira coisa que o usuário pediu corretamente: *"O certo é escrevê-lo na
íntegra."*

**Correção.** Se o PDF traz erro de digitação, o erro aparece. Isto é transcrição,
não edição.

**Preenchimento.** PDF sem camada de texto fica com `texto = null` e um `motivo`
legível. A tela diz que não foi possível transcrever e oferece o original. Um
plano mal extraído é pior que nenhum.

### O que a tela promete

Cada plano publicado é rotulado **"transcrição automática do PDF oficial"**, com
link para o arquivo no TSE ao lado. O leitor sabe que está lendo uma extração, não
o documento diagramado — e tem como conferir.

## Consequência

Uma dependência nova: **`pypdf`**. É a única do núcleo que não fala com nuvem. Ler
PDF em stdlib exigiria implementar o formato, e uma transcrição torta deturpa a
proposta de uma pessoa real — não é lugar para economia de dependência.

Ganho colateral que não era o objetivo: **206 páginas com texto substantivo real**.
Quem busca "o que fulano propõe sobre saúde" passa a ter onde chegar. É, de longe,
o conteúdo mais indexável do projeto — e o dado que o usuário identificou como
"peça fundamental", por não estar disponível em lugar nenhum de forma consultável.

## O que continua valendo da ADR-013

Tudo sobre **alcance**: a Lei 9.504/97 (art. 11, §1º, IX) exige plano de Prefeito,
Governador e Presidente. Senador é majoritário e **não** consta da lista. A
distinção entre "não apresentou" e "não é exigido" segue sendo a parte mais
importante desta feature, e não muda.
