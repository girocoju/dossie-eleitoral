{#
  A SERIE QUE SO' EXISTE SE FOR CAPTURADA AGORA.

  O TSE republica o pacote de candidaturas todo dia ate' 04/10/2026, mas publica
  sempre o ESTADO ATUAL — nunca o historico. Em 27/08/2026, 64,3% das candidaturas
  estavam "aguardando julgamento". Cada uma vai virar deferida, indeferida,
  renunciada ou substituida em algum dia especifico entre agora e a eleicao, e esse
  "quando" desaparece no instante em que a proxima versao do arquivo sobe.

  Depois de 04/10 essa serie nao pode ser reconstruida de fonte nenhuma. Este
  snapshot e' a unica coisa no projeto que tem prazo.

  Estrategia `check` e nao `timestamp`: o arquivo nao traz data de atualizacao por
  registro, e `_extracted_at` muda a cada carga — usa-lo criaria uma versao nova
  todo dia mesmo sem nada ter mudado. Com `check`, uma linha nova so' nasce quando
  um dos campos observados muda de valor.

  `hard_deletes: new_record` registra tambem o DESAPARECIMENTO de uma candidatura
  do arquivo, que e' informacao: significa que o registro foi cancelado na origem.
#}

{% snapshot snap_candidatura_2026 %}

{{
  config(
    target_schema = 'marts',
    unique_key    = 'sk_candidatura',
    strategy      = 'check',
    check_cols    = [
      'situacao_julgamento',
      'situacao_candidatura',
      'detalhe_situacao',
      'situacao_cassacao',
      'situacao_urna',
      'foi_substituido',
      'sq_substituido',
      'sigla_partido',
      'sq_coligacao',
      'nome_coligacao',
      'nome_urna',
      'cod_cargo'
    ],
    hard_deletes  = 'new_record'
  )
}}

select
    sk_candidatura,
    sq_candidato,
    ano_eleicao,
    sg_uf,
    sg_ue,
    cod_cargo,
    nome_urna,
    sigla_partido,
    sq_coligacao,
    nome_coligacao,
    situacao_candidatura,
    situacao_julgamento,
    detalhe_situacao,
    situacao_cassacao,
    situacao_urna,
    foi_substituido,
    sq_substituido,
    _extracted_at
from {{ ref('stg_tse__candidaturas') }}
where ano_eleicao = {{ var('ano_eleicao_atual') }}
  and nr_turno = 1

{% endsnapshot %}
