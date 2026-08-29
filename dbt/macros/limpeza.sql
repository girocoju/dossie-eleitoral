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
    Traduz `DS_SIT_TOT_TURNO` para "ocupou a cadeira". TRES estados, nao dois:

        TRUE    o TSE publicou que foi eleito
        FALSE   o TSE publicou que nao foi
        NULL    o TSE NAO PUBLICOU o resultado

    A versao anterior fazia `COALESCE(..., FALSE)`, com o argumento de que "ainda
    nao eleito nao e' eleito". O argumento vale para 2026, onde a eleicao nem
    ocorreu. Nao vale para o passado — e ali o COALESCE virava uma AFIRMACAO
    FALSA sobre uma pessoa real.

    Em 2006 o TSE nao publica `DS_SIT_TOT_TURNO` para NENHUM dos 8 candidatos a
    Presidente: todos chegam `#NULO#`, `cd = -1` (lacuna L-16). Com o COALESCE, a
    ficha do Lula dizia "2006 · Presidente · Nao eleito". Ele foi eleito, em
    segundo turno, com 58,3 milhoes de votos. O erro esteve no ar e foi o proprio
    usuario quem viu.

    Sao 13.834 candidaturas de 1998-2022 nessa situacao, mais as 20.769 de 2026.
    Ausencia de dado nunca vira afirmacao — e' a regra 5 do CLAUDE.md, e este
    macro era o unico lugar do projeto que a violava.

    Quem precisa de booleano para FILTRAR ("liste os eleitos") escreve o
    `COALESCE(..., FALSE)` no ponto de uso, onde a intencao fica visivel.
    `LOGICAL_OR` e `COUNTIF` ja' ignoram NULL e continuam corretos sem mudanca.
  -#}
  CASE
    WHEN {{ limpa(coluna_situacao_turno) }} IS NULL THEN NULL
    ELSE {{ sem_acento(limpa(coluna_situacao_turno)) }} IN (
      'ELEITO',
      'ELEITO POR QP',
      'ELEITO POR MEDIA',
      'MEDIA'
    )
  END
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
