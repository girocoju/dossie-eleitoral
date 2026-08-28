/*
  Candidatura que some da publicacao do TSE e' um evento REAL, e por isso nao e'
  mais tratada como erro de integridade — mas continua tendo que ser rara.

  O que aconteceu: `fct_mudanca_candidatura` vem do snapshot, que preserva o que
  o TSE ja' publicou. `fct_candidatura` vem da carga de hoje. Uma candidatura
  cancelada, retirada ou corrigida existe no primeiro e nao no segundo. O teste de
  relacionamento entre os dois acusava isso como quebra, quando e' justamente a
  informacao que o projeto existe para guardar: o TSE publica o estado atual, e
  quem so' le' a publicacao de hoje nunca sabe que aquela candidatura existiu.

  Medido em 28/08/2026: 4 candidaturas sumidas, 8 linhas de mudanca.

  O TETO AINDA PROTEGE o caso grave. Se a proporcao disparar, a causa nao e'
  cancelamento de registro: e' `sk_candidatura` montada de forma diferente entre o
  snapshot e a carga, ou uma carga do TSE que veio truncada e "sumiu" com milhares
  de candidaturas que continuam existindo.

  Teto de 2% das linhas de mudanca.
*/

with contagem as (

    select
        count(*)                                as mudancas,
        countif(not consta_na_lista_atual)      as de_candidatura_sumida
    from {{ ref('fct_mudanca_candidatura') }}

)

select
    mudancas,
    de_candidatura_sumida,
    round(de_candidatura_sumida / nullif(mudancas, 0), 4) as taxa
from contagem
where de_candidatura_sumida > mudancas * 0.02
