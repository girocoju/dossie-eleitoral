/*
  Zero em `fct_patrimonio_declarado` nao quer dizer patrimonio zero (L-27).

  O arquivo de bens de 2006 publica itens com valor zerado: 10,3% dos itens
  daquele ano, contra ~0% em todos os outros. O efeito no total e' brutal —
  6.699 das 19.263 candidaturas de 2006 somam exatamente zero, contra 26 em
  2022 e 14 em 2026.

  Isso nao e' um fato sobre as pessoas de 2006, e' um fato sobre o arquivo. E' o
  segundo problema conhecido dele; o primeiro e' a L-16, o desfecho da eleicao
  que ele nao publica.

  A ficha mostra as declaracoes lado a lado. Uma linha "R$ 0 em 2006" ao lado de
  "R$ 500 mil em 2026" faria o leitor concluir uma historia que o dado nao conta
  — e seria ausencia virando afirmacao, que a Regra 5 proibe.

  O modelo filtra com `having max(vl_total) > 0`. Este teste trava a volta desse
  filtro: se alguem o retirar, zeros voltam a aparecer e a ficha volta a contar
  a historia errada.
*/

select
    id_pessoa,
    ano_eleicao,
    vl_total_declarado
from {{ ref('fct_patrimonio_declarado') }}
where vl_total_declarado <= 0
