/*
  A classe `outra` tem que continuar sendo residuo, nao o balde principal.

  A separacao por classe e' o que impede o painel de dizer que um deputado com 400
  requerimentos de retirada de pauta trabalhou 33x mais que um com 12 projetos de
  lei. Se a Camara criar um tipo novo de alto volume e ele cair em `outra`, essa
  protecao se desfaz sem aviso: o numero continua aparecendo, so' que sem
  significado.

  Ja' pegou um caso real. Na primeira classificacao, `outra` era a MAIOR classe de
  2025 (57.907 de 109.582) porque `PRL` — parecer de relator, 15.501 itens — e
  `RPD` — retirada de pauta, 31.479 — nao estavam mapeados. Parecer de relator nem
  autoria e'.

  Teto de 15%. Medido em 28/08/2026: 5,8% na legislatura 2023-2026.
*/

with proporcao as (

    select
        sum(if(classe_proposicao = 'outra', qt_proposicoes, 0)) as em_outra,
        sum(qt_proposicoes)                                     as total
    from {{ ref('fct_atividade_legislativa') }}

)

select
    em_outra,
    total,
    round(em_outra / total, 4) as taxa
from proporcao
where em_outra > total * 0.15
