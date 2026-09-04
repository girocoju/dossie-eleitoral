{{
  config(
    materialized = 'view',
    description  = 'Emendas parlamentares, arquivo unico cumulativo, tipado (F-27).'
  )
}}

/*
  Uma linha por (emenda, destino). O Portal publica UM arquivo cumulativo — o ano
  no endereco e' ignorado, e os treze anos devolvem o mesmo sha256 (ver o
  cabecalho de `ingest/emendas.py`).

  São 94.463 linhas cobrindo emendas de 2014 a 2026, com o valor JA' acumulado de
  empenho, liquidacao e pagamento. O ano de verdade e' `ano_emenda`.

  ── NAO HA' O QUE SOMAR ENTRE ARQUIVOS ──

  A primeira versao deste pipeline supunha um arquivo por exercicio e se
  preocupava com dupla contagem: uma emenda de 2020 apareceria empenhada no
  arquivo de 2020 e paga no de 2022. A preocupacao era correta e o pressuposto
  nao: ha' um arquivo so'. A tela mostra uma linha por ANO DA EMENDA, que e' a
  unica dimensao temporal que a fonte oferece.

  ── AUTOR COLETIVO NAO E' PESSOA ──

  `autor_e_pessoa` chega pronto da ingestao. RELATOR GERAL move bilhoes e nao e'
  de ninguem em particular; bancada e comissao sao assinatura de grupo. Nenhum
  dos tres pode ir para a ficha de um candidato.

  As linhas continuam aqui, de proposito: sao 17% do arquivo, e sumir com elas
  tornaria impossivel dizer na tela que existem.
*/

select
    ano_emenda,
    nullif(codigo, '')                                  as codigo,
    nullif(numero, '')                                  as numero,
    nullif(tipo, '')                                    as tipo,

    nullif(autor, '')                                   as autor,
    nullif(autor_normalizado, '')                       as autor_normalizado,
    autor_e_pessoa,
    nullif(cod_autor, '')                               as cod_autor,

    -- `SEM INFORMACAO` e' o rotulo do Portal para autoria nao publicada. Vira
    -- uma marca propria porque a tela precisa contar quanto disso existe (L-29).
    autor_normalizado is null
      or autor_normalizado = ''
      or contains_substr(autor_normalizado, 'SEM INFORMA')  as autoria_nao_publicada,

    nullif(uf, '')                                      as sg_uf,
    nullif(municipio, '')                               as municipio,
    nullif(cod_municipio, '')                           as cod_municipio,
    nullif(funcao, '')                                  as funcao,
    nullif(subfuncao, '')                               as subfuncao,
    nullif(programa, '')                                as programa,
    nullif(acao, '')                                    as acao,

    vl_empenhado,
    vl_liquidado,
    vl_pago,
    vl_restos_pagos,

    _extracted_at

from {{ source('raw_tesouro', 'emendas') }}
