/*
  F-14: proposta de governo e' exigida por lei so' de cargos majoritarios —
  Presidente (1), Governador (3) e Senador (5).

  Uma candidatura proporcional com `tem_proposta_governo = true` significaria que
  a consulta ao DivulgaCandContas foi feita para quem nao deveria, ou que o
  `codTipo = 5` nao quer dizer o que achamos que quer.

  Falha se aparecer proposta em cargo que nao a exige.
*/

select
    sk_candidatura,
    cod_cargo,
    sg_ue,
    nome_arquivo_proposta
from {{ ref('fct_candidatura') }}
where tem_proposta_governo
  and not proposta_obrigatoria
