/*
  SPEC 5, "Janela de mandato": Governador/Presidente 4 anos, Senador 8, Deputados 4,
  sempre comecando em ano_eleicao + 1.

  Falha se alguma janela nao respeitar a duracao declarada no seed de cargos.
*/

select
    sk_mandato,
    cod_cargo,
    ano_eleicao,
    ano_inicio,
    ano_fim,
    duracao_mandato_anos
from {{ ref('fct_mandato') }}
where ano_inicio != ano_eleicao + 1
   or ano_fim - ano_inicio + 1 != duracao_mandato_anos
