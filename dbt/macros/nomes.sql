{#
  Sem este macro o dbt concatena `<dataset do target>_<schema custom>` e cria
  `marts_stg` e `marts_marts`. O SPEC 4 fixa os nomes dos datasets — `stg` e
  `marts` —, e o gerador do site aponta para eles. Entao o schema declarado no modelo
  vale como esta'.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
