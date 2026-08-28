/*
  O resultado primario do Governo Central tem que bater com receita liquida menos
  despesa primaria.

  Diferente do teste estadual, aqui NADA e' calculado pelo projeto: as tres series
  vem OBSERVADAS de tres linhas independentes da tabela 2.1 do RTN. Justamente por
  isso a conferencia vale — ela prova que as tres rubricas certas foram lidas.

  Se o Tesouro reordenar as linhas da planilha, ou se um prefixo de rubrica passar
  a casar com outra linha (a numeracao muda entre edicoes), o resultado deixa de
  fechar com as parcelas e o teste falha. Sem isso, o painel exibiria um deficit de
  outra rubrica sem ninguem perceber — foi exatamente esse tipo de erro silencioso
  que a L-22 corrigiu.

  Tolerancia de R$ 1 milhao: a planilha esta' em R$ milhoes com muitas casas
  decimais, e a soma das parcelas arredonda de forma levemente diferente do total
  publicado.
*/

with parcelas as (

    select
        ano,
        max(if(cod_indicador = 'RECEITA_LIQUIDA_UNIAO',    valor, null)) as receita,
        max(if(cod_indicador = 'DESPESA_PRIMARIA_UNIAO',   valor, null)) as despesa,
        max(if(cod_indicador = 'RESULTADO_PRIMARIO_UNIAO', valor, null)) as resultado
    from {{ ref('fct_indicador_uf_ano') }}
    where sg_uf = 'BR'
      and cod_indicador in (
        'RECEITA_LIQUIDA_UNIAO', 'DESPESA_PRIMARIA_UNIAO', 'RESULTADO_PRIMARIO_UNIAO'
      )
    group by ano

)

select
    ano,
    receita,
    despesa,
    resultado,
    receita - despesa as esperado,
    abs(resultado - (receita - despesa)) as diferenca
from parcelas
where receita is not null
  and despesa is not null
  and resultado is not null
  and abs(resultado - (receita - despesa)) > 1000000
