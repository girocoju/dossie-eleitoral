/*
  O resultado orcamentario e' derivado: receita liquida menos despesa empenhada.
  Este teste garante que a subtracao no mart continua batendo com as duas parcelas
  que a alimentam — se alguem mexer no `fct_indicador_uf_ano` e inverter o sinal,
  ou trocar despesa empenhada por paga, o numero muda sem ninguem notar.

  Tolerancia de R$ 1,00 para arredondamento de ponto flutuante.
*/

with parcelas as (

    select
        sg_uf,
        ano,
        max(if(cod_indicador = 'RECEITA_ESTADUAL', valor, null))         as receita,
        max(if(cod_indicador = 'DESPESA_ESTADUAL', valor, null))         as despesa,
        max(if(cod_indicador = 'RESULTADO_ORCAMENTARIO', valor, null))   as resultado
    from {{ ref('fct_indicador_uf_ano') }}
    where cod_indicador in ('RECEITA_ESTADUAL', 'DESPESA_ESTADUAL', 'RESULTADO_ORCAMENTARIO')
    group by sg_uf, ano

)

select
    sg_uf,
    ano,
    receita,
    despesa,
    resultado,
    resultado - (receita - despesa) as diferenca
from parcelas
where receita is not null
  and despesa is not null
  and abs(resultado - (receita - despesa)) > 1
