/*
  Constituicao 0.2: nenhum numero de UF pode chegar a tela sem comparador.
  Como o comparador vive na MESMA linha do fato, basta garantir que ele exista
  sempre que houver um valor nacional publicado para aquele indicador e ano.

  Falha se uma UF tiver valor num (indicador, ano) em que o Brasil tambem tem
  valor, mas `valor_brasil` estiver NULL — o que so' aconteceria por erro de join.
*/

with nacional as (

    select cod_indicador, ano
    from {{ ref('fct_indicador_uf_ano') }}
    where sg_uf = 'BR' and valor is not null

)

select
    f.cod_indicador,
    f.sg_uf,
    f.ano
from {{ ref('fct_indicador_uf_ano') }} as f
inner join nacional as n using (cod_indicador, ano)
where f.sg_uf != 'BR'
  and f.valor is not null
  and f.valor_brasil is null
