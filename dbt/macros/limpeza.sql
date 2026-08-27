{#
  Macros de limpeza das fontes brasileiras.

  Toda a camada `raw_*` chega em STRING (SPEC 4). Estes macros sao o unico lugar
  onde a decisao "como o TSE representa ausencia" e "como o Brasil escreve numero
  e data" existe — se o TSE mudar uma sentinela, muda-se aqui e nada mais.
#}

{% macro limpa(coluna) -%}
  {#- Trim + sentinelas do TSE viram NULL. Espelha `ingest.common.textnorm.clean`. -#}
  NULLIF(
    NULLIF(
      NULLIF(
        NULLIF(
          NULLIF(
            NULLIF(NULLIF(TRIM({{ coluna }}), ''), '#NULO#'),
          '#NULO'),
        '#NE#'),
      '#NE'),
    '#NI#'),
  'N/A')
{%- endmacro %}


{% macro sem_acento(coluna) -%}
  {#- `MÉDIA` -> `MEDIA`. Usado para comparar rotulos do TSE sem depender de acento. -#}
  UPPER(REGEXP_REPLACE(NORMALIZE({{ coluna }}, NFD), r'\pM', ''))
{%- endmacro %}


{% macro data_br(coluna) -%}
  {#- `31/12/1970` -> DATE. Datas-sentinela (<=1900, >=9999) viram NULL. -#}
  (
    SELECT
      CASE
        WHEN d IS NULL THEN NULL
        WHEN EXTRACT(YEAR FROM d) <= 1900 OR EXTRACT(YEAR FROM d) >= 9999 THEN NULL
        ELSE d
      END
    FROM (SELECT COALESCE(
      SAFE.PARSE_DATE('%d/%m/%Y', {{ limpa(coluna) }}),
      SAFE.PARSE_DATE('%Y-%m-%d', {{ limpa(coluna) }}),
      SAFE.PARSE_DATE('%d-%m-%Y', {{ limpa(coluna) }})
    ) AS d)
  )
{%- endmacro %}


{% macro decimal_br(coluna) -%}
  {#-
    `1.234.567,89` -> 1234567.89, mas `3176572.53` -> 3176572.53.
    O TSE alterna entre os dois formatos (conferido: bens usam virgula,
    VR_DESPESA_MAX_CAMPANHA de 2026 usa ponto). A regra e' olhar qual separador
    aparece por ULTIMO: esse e' o decimal.
  -#}
  SAFE_CAST(
    CASE
      WHEN {{ limpa(coluna) }} IS NULL THEN NULL
      WHEN STRPOS(REVERSE({{ coluna }}), ',') > 0
       AND (STRPOS(REVERSE({{ coluna }}), ',') < STRPOS(REVERSE({{ coluna }}), '.')
            OR STRPOS(REVERSE({{ coluna }}), '.') = 0)
        THEN REPLACE(REPLACE(TRIM({{ coluna }}), '.', ''), ',', '.')
      ELSE REPLACE(TRIM({{ coluna }}), ',', '')
    END
    AS FLOAT64
  )
{%- endmacro %}


{% macro sim_nao(coluna) -%}
  {#- `S`/`N` do TSE -> BOOL. Qualquer outra coisa (inclusive `#NE`) vira NULL. -#}
  CASE {{ sem_acento(limpa(coluna)) }}
    WHEN 'S' THEN TRUE
    WHEN 'SIM' THEN TRUE
    WHEN 'N' THEN FALSE
    WHEN 'NAO' THEN FALSE
  END
{%- endmacro %}


{% macro inteiro(coluna) -%}
  SAFE_CAST({{ limpa(coluna) }} AS INT64)
{%- endmacro %}


{% macro foi_eleito(coluna_situacao_turno) -%}
  {#-
    Traduz `DS_SIT_TOT_TURNO` para "ocupou a cadeira".
    Os rotulos do TSE variam entre anos e acentuacao: ELEITO, ELEITO POR QP,
    ELEITO POR MEDIA, MEDIA. `#NULO`/`-1` (eleicao ainda nao ocorrida, caso de
    2026) devolve FALSE — nao NULL — porque "ainda nao eleito" nao e' "eleito".
  -#}
  COALESCE({{ sem_acento(limpa(coluna_situacao_turno)) }} IN (
    'ELEITO',
    'ELEITO POR QP',
    'ELEITO POR MEDIA',
    'MEDIA'
  ), FALSE)
{%- endmacro %}


{% macro variacao_pct(fim, inicio) -%}
  {#-
    Variacao percentual segura: divisao por zero e base negativa devolvem NULL
    em vez de um numero que o leitor interpretaria como real.
  -#}
  CASE
    WHEN {{ inicio }} IS NULL OR {{ fim }} IS NULL THEN NULL
    WHEN {{ inicio }} <= 0 THEN NULL
    ELSE SAFE_DIVIDE({{ fim }} - {{ inicio }}, {{ inicio }}) * 100
  END
{%- endmacro %}
