/*
  Nenhuma candidatura de uma eleicao que ainda nao ocorreu pode ter votos.

  Em 28/08/2026 isso vale para o pleito inteiro de 2026: votos NULL ali nao sao
  lacuna de dado, sao o calendario. Se aparecer voto em 2026 antes de 04/10,
  alguma coisa esta' muito errada — pacote trocado, ano mal atribuido, ou juncao
  cruzando eleicoes.
*/

select
    sk_candidatura,
    ano_eleicao,
    cod_cargo,
    votos_nominais
from {{ ref('fct_candidatura') }}
where ano_eleicao = {{ var('ano_eleicao_atual') }}
  and votos_nominais is not null
