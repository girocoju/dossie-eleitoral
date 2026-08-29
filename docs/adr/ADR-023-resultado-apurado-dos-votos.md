# ADR-023 — Resultado apurado dos votos, onde o TSE não publica

**Status:** Aceita · **Data:** 2026-08-29 · **Fecha parcialmente:** L-16 · **Relacionada:** ADR-009

## Contexto: um erro que esteve publicado

A ficha de Luiz Inácio Lula da Silva, no ar em `datadubaintel.com/dossie`, trazia:

```
2006 · Presidente · BR · PT · Não eleito
```

Ele foi eleito, em segundo turno, com 58.295.042 votos.

O erro não veio de dado errado. Veio de **ausência de dado transformada em
afirmação**. O TSE não publica `DS_SIT_TOT_TURNO` no `consulta_cand` para nenhum
dos 8 candidatos a Presidente de 2006 — todos chegam `#NULO#`, `cd = -1`. O macro
`foi_eleito` fazia `COALESCE(..., FALSE)`, e "não sei" virava "não".

São **13.834 candidaturas de 1998-2022** nessa situação, mais as 20.769 de 2026.

Nenhum teste pegou. `dbt build` verde, 238 testes. Quem viu foi o usuário, abrindo
a própria página. É o modo de falha da Regra 6 do `CLAUDE.md` — só que sobre uma
**pessoa**, não sobre um indicador.

## Duas decisões distintas

### 1. `foi_eleito` passa a ter três estados

| | |
|---|---|
| `TRUE` | o TSE publicou que foi eleito |
| `FALSE` | o TSE publicou que não foi |
| `NULL` | **o TSE não publicou** |

O `not_null` no schema saiu junto — era ele que obrigava o macro a inventar um
valor. Um teste que força a fonte a mentir é pior que teste nenhum.

`LOGICAL_OR` e `COUNTIF` já ignoram `NULL` e seguem corretos sem mudança. Quem
precisa de booleano para filtrar escreve `COALESCE(..., FALSE)` no ponto de uso,
onde a intenção fica visível.

### 2. Onde o TSE cala e a aritmética decide, apuramos

`int_resultado_por_votos` calcula o resultado de cargo **majoritário** a partir de
dois conjuntos oficiais que já estavam no lake:

```
raw_tse.votacao   votos por candidatura e turno
raw_tse.vagas     cadeiras em disputa naquela UE
```

Elegem-se os N mais votados do último turno realizado, com N vindo do TSE — não
há número fixo no código. Isso importa: o Senado renovou 1 vaga por estado em
2006 e 2 em 2018.

**Isto não é preencher buraco de dado.** A Regra 5 proíbe inventar o que não
existe. Aqui nada é inventado: é uma função aritmética de dois dados oficiais,
sem discrição. Quem teve mais voto no segundo turno ganhou o segundo turno.

## Só majoritário — e isso não é preguiça

Deputado (cargos 6, 7, 8) fica **fora**. Cadeira proporcional não vai para quem
teve mais voto pessoal: depende de quociente eleitoral, quociente partidário,
sobras e do desempenho da legenda inteira. Um "top N por votos" ali produziria
uma lista de eleitos **errada com aparência de certa** — pior que a ausência que
esta ADR corrige.

## A confiança foi medida, não assumida

Uma apuração que se aplica onde não há gabarito precisa provar que acerta onde
há. A mesma regra foi rodada sobre os anos em que o TSE **publica** o resultado:

| | |
|---|---|
| Acertos | **2.636** |
| Divergências | 4 |
| Precisão | **99,85%** |
| Presidente | **50 de 50** |

As 4 divergências são cassação e eleição suplementar — casos em que quem ocupou a
cadeira não foi quem teve mais voto na urna, e que contagem nenhuma tem como
saber (2014 · AM · Amazonino Mendes; 2018 · MT · Fávaro).

Elas não chegam à tela: **o TSE tem sempre precedência**. A apuração só fala onde
ele calou. `assert_resultado_derivado_bate_com_o_tse` trava isso, com teto de 10
divergências — não zero, porque a próxima cassação é evento normal da vida
eleitoral e não defeito deste código.

## O que a tela diz

O resultado apurado aparece marcado **`apurado`** na própria célula, com tooltip
explicando a origem — não só numa nota de rodapé. Quem lê a linha precisa saber
de onde veio aquela palavra sem procurar.

A nota da tabela explica a eleição de 2006 por extenso, incluindo que cargos
proporcionais nunca são apurados assim.

**Ganho colateral que não era o objetivo.** A coluna de votos mostrava, para
eleição de dois turnos, a **soma** dos turnos — 117.605.503 para Lula em 2022, um
número que não existe em lugar nenhum e que ninguém consegue conferir. Agora
mostra o votação do turno decisivo, 60.345.999, com o turno indicado. Verificável
contra qualquer fonte.

**Distinção nova, do mesmo trabalho.** Candidatura indeferida deixa de aparecer
como "não eleito": Lula em 2018 estava `INAPTO` e não perdeu eleição nenhuma —
ele não concorreu. A tela agora diz *candidatura indeferida*.

## Consequência: um mandato voltou

`fct_mandato` passa a usar o resultado final. O segundo mandato de Lula
(2007-2010) não existia na tabela — havia sumido junto com o resultado de 2006 —
e com ele sumia a janela 2007-2010 do bloco socioeconômico.

Não há Presidente de 2006 em `fct_mandato` era um buraco que ninguém tinha
notado, e que só apareceu porque o erro visível na tela obrigou a puxar o fio.

## O que continua faltando

1998 não tem votação no lake, então nada é apurado ali — a apuração devolve
`NULL` em vez de chutar, porque com votos zerados todos empatam em primeiro.
Cargos proporcionais sem resultado publicado seguem sem resultado. Ver L-16.
