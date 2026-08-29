/*
  Ausencia de resultado NAO pode virar "nao eleito".

  Este teste existe por causa de um erro que esteve publicado: a ficha do Lula
  trazia "2006 · Presidente · Nao eleito". Ele foi eleito, em segundo turno, com
  58,3 milhoes de votos. O TSE nao publica `DS_SIT_TOT_TURNO` para NENHUM dos 8
  candidatos a Presidente de 2006 — todos chegam `#NULO#` (L-16) — e o macro
  `foi_eleito` fazia `COALESCE(..., FALSE)`, transformando "nao sei" em "nao".

  Nenhum teste automatico pegou. `dbt build` verde, 238 testes, e o erro ficou no
  ar ate' o usuario abrir a propria ficha e ver. E' exatamente o modo de falha da
  regra 6 do CLAUDE.md, so' que sobre uma PESSOA em vez de um indicador.

  O que este teste trava: se alguem reintroduzir o COALESCE, ou o `not_null` que
  o obrigava a existir, uma eleicao inteira volta a ser declarada perdida por
  todos os concorrentes — que e' o sintoma detectavel, porque e' impossivel.

  A regra: em toda eleicao com resultado publicado para ALGUEM naquele cargo e
  unidade eleitoral, tem que haver ao menos um eleito. Zero eleitos com
  resultado publicado para todos e' contradicao — ou o cargo nao foi disputado,
  e ai' ninguem tem resultado.
*/

with disputas as (

    select
        ano_eleicao,
        cod_cargo,
        sg_ue,
        countif(foi_eleito is true)     as eleitos,
        countif(foi_eleito is false)    as derrotados,
        countif(foi_eleito is null)     as sem_resultado,
        count(*)                        as candidaturas
    from {{ ref('fct_candidatura') }}
    -- 2026 inteiro ainda nao foi apurado: tudo NULL, e esta' correto.
    where ano_eleicao < 2026
    group by ano_eleicao, cod_cargo, sg_ue

)

select *
from disputas
/*
  A contradicao: o TSE publicou o desfecho de TODAS as candidaturas daquela
  disputa, e nenhuma foi eleita. Alguem ocupou a cadeira.

  Uma disputa em que NINGUEM tem resultado publicado (o caso de 2006) nao cai
  aqui — e' lacuna conhecida, nao afirmacao falsa. O que nao pode existir e'
  "todo mundo perdeu".
*/
where sem_resultado = 0 and eleitos = 0
