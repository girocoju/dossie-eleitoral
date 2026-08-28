/*
  F-13: nenhuma foto pode apontar para candidatura que nao existe.

  Uma foto orfa significaria que o `sq_candidato` do nome do arquivo nao bate com
  o do `consulta_cand` — ou seja, que os dois pacotes do TSE estao dessincronizados,
  ou que a nossa `sk_candidatura` foi montada errado. Conferido em 27/08/2026: zero
  orfas no Acre.
*/

select
    f.sk_candidatura,
    f.sg_ue,
    f.url_foto
from {{ ref('stg_tse__fotos') }} as f
left join {{ ref('dim_candidato') }} as d using (sk_candidatura)
where d.sk_candidatura is null
