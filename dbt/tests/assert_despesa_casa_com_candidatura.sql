/*
  Guarda a substituicao de chave em `stg_tse__despesas_campanha`.

  O arquivo de despesa do TSE nao traz `sg_ue`, so' `sg_uf`. Em eleicao GERAL os
  dois sao identicos — conferido nos 43.610 lancamentos de receita, onde ambos
  existem: zero divergencias. Entao a chave de despesa usa `sg_uf` no lugar.

  Em eleicao MUNICIPAL isso deixa de valer: `sg_ue` vira codigo de municipio, e a
  chave montada com `sg_uf` fundiria todas as candidaturas de um estado numa so'.
  A despesa de um vereador de Sorocaba entraria na ficha de outro de Campinas.

  O modo de falha e' silencioso — a tabela nao quebra, ela mente. Por isso o teste
  nao confere `sg_ue`: confere se as despesas CASAM com candidaturas reais. Se a
  chave estiver errada, o casamento despenca antes de qualquer numero ficar
  estranho na tela.

  Piso de 95%. Abaixo disso e' erro de chave, nao candidatura indeferida.
*/

with despesas as (

    select distinct sk_candidatura
    from {{ ref('stg_tse__despesas_campanha') }}

),

casamento as (

    select
        count(*)                                        as total,
        countif(c.sk_candidatura is not null)           as casadas
    from despesas d
    left join {{ ref('fct_candidatura') }} c using (sk_candidatura)

)

select total, casadas, round(casadas / total, 4) as taxa
from casamento
where casadas < total * 0.95
