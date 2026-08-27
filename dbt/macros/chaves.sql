{#
  Chave de candidatura.

  `sq_candidato` NAO serve como chave sozinho: ele so' e' globalmente unico a
  partir de 2010. Em 2002 e 2006 e' um contador por unidade eleitoral e o mesmo
  numero aparece em ate' 27 UFs (conferido nos oito anos em 27/08/2026). Usar
  `sq_candidato` puro fundiria pessoas diferentes de estados diferentes numa so'.

  A chave minima que e' unica em TODOS os anos e' (ano_eleicao, sg_ue, sq_candidato).
  Este macro a materializa como uma unica coluna, para as junções ficarem legiveis
  e para o Power BI ter uma chave simples.
#}

{% macro sk_candidatura(ano_eleicao='ano_eleicao', sg_ue='sg_ue', sq_candidato='sq_candidato') -%}
  concat(
    cast({{ ano_eleicao }} as string), '-',
    coalesce({{ sg_ue }}, 'ND'), '-',
    cast({{ sq_candidato }} as string)
  )
{%- endmacro %}
