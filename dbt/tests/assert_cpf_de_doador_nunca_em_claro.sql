/*
  A garantia central da ADR-020, verificada no dado e nao so' no codigo.

  O arquivo do TSE traz `NR_CPF_CNPJ_DOADOR` em texto puro — um CPF valido e
  legivel por linha de pessoa fisica. A ingestao hasheia antes de gravar, mas
  "a ingestao faz a coisa certa" e' uma promessa sobre codigo. Este teste e' a
  verificacao sobre o dado que efetivamente esta' no lake.

  O que ele procura: qualquer coluna de texto do financiamento contendo algo com
  a forma de CPF — 11 digitos que nao sao um CNPJ truncado nem um hash.

  `doador_cnpj` entra no teste de proposito. E' a coluna que mais correria risco:
  se um dia o TSE mudar o layout e um CPF cair no lugar do CNPJ, o codigo nao
  reclamaria — o campo aceita string. Aqui reclama.

  `doador_cpf_hash` e `fornecedor_cpf_hash` ficam de fora: sao hex de 64
  caracteres por construcao, nunca 11 digitos. Se um deles virar 11 digitos, e'
  porque o hash parou de ser aplicado — e ai' cai nos outros campos tambem.

  Falha aqui NAO e' um teste chato: e' CPF de cidadao brasileiro publicado num
  site. E' a unica falha deste projeto que fere alguem que nao se candidatou a nada.
*/

{% set colunas_receita = ['doador_cnpj', 'nome_doador', 'doador_uf', 'doador_ramo'] %}
{% set colunas_despesa = ['fornecedor_cnpj', 'nome_fornecedor', 'fornecedor_uf'] %}

with suspeitos as (

    {% for coluna in colunas_receita %}
    select
        'stg_tse__financiamento' as modelo,
        '{{ coluna }}'           as coluna,
        sq_receita               as chave
    from {{ ref('stg_tse__financiamento') }}
    where regexp_contains({{ coluna }}, r'^\d{11}$')
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

    union all

    {% for coluna in colunas_despesa %}
    select
        'stg_tse__despesas_campanha' as modelo,
        '{{ coluna }}'               as coluna,
        sq_despesa                   as chave
    from {{ ref('stg_tse__despesas_campanha') }}
    where regexp_contains({{ coluna }}, r'^\d{11}$')
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select modelo, coluna, count(*) as ocorrencias
from suspeitos
group by modelo, coluna
