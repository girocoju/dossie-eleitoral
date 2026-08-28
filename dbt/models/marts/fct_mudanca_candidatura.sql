{{
  config(
    materialized = 'table',
    cluster_by   = ['sg_uf', 'cod_cargo'],
    description  = 'Cada mudanca observada numa candidatura de 2026, com a data em que foi vista. Serie irreproduzivel apos 04/10/2026.'
  )
}}

/*
  Transforma o SCD2 de `snap_candidatura_2026` em eventos legiveis: uma linha por
  MUDANCA observada, com o valor antigo, o novo e o dia em que a mudanca apareceu.

  O que isso responde, e nenhuma outra fonte responde:
    - em que dia cada candidatura foi deferida ou indeferida;
    - quanto tempo o TSE levou, por UF e por cargo, para julgar;
    - quantas candidaturas trocaram de partido ou de coligacao depois do registro;
    - quem foi substituido, e quando.

  Precisao temporal: a data e' a da CAPTURA, nao a do ato. Se o pipeline roda uma
  vez por dia, a mudanca e' localizada com precisao de um dia — e se ficar dois
  dias sem rodar, com precisao de dois. `dias_desde_observacao_anterior` deixa essa
  incerteza explicita em vez de escondida, para que ninguem leia a data como se
  fosse a data do despacho.
*/

with versoes as (

    select
        sk_candidatura,
        sq_candidato,
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
        dbt_valid_from,
        dbt_valid_to,
        row_number() over (partition by sk_candidatura order by dbt_valid_from) as versao
    from {{ ref('snap_candidatura_2026') }}

),

com_anterior as (

    select
        v.*,
        lag(situacao_julgamento) over j    as situacao_julgamento_anterior,
        lag(situacao_candidatura) over j   as situacao_candidatura_anterior,
        lag(sigla_partido) over j          as sigla_partido_anterior,
        lag(nome_coligacao) over j         as nome_coligacao_anterior,
        lag(nome_urna) over j              as nome_urna_anterior,
        lag(foi_substituido) over j        as foi_substituido_anterior,
        lag(dbt_valid_from) over j         as observacao_anterior
    from versoes as v
    window j as (partition by sk_candidatura order by dbt_valid_from)

)

select
    sk_candidatura,
    sq_candidato,
    sg_uf,
    sg_ue,
    cod_cargo,
    nome_urna,
    versao,
    date(dbt_valid_from)                                    as data_observacao,
    date(observacao_anterior)                               as data_observacao_anterior,
    date_diff(date(dbt_valid_from), date(observacao_anterior), day)
                                                            as dias_desde_observacao_anterior,
    dbt_valid_to is null                                    as is_estado_atual,

    situacao_julgamento_anterior,
    situacao_julgamento,
    situacao_candidatura_anterior,
    situacao_candidatura,
    sigla_partido_anterior,
    sigla_partido,
    nome_coligacao_anterior,
    nome_coligacao,
    nome_urna_anterior,
    detalhe_situacao,
    situacao_cassacao,
    situacao_urna,
    foi_substituido,
    sq_substituido,

    -- que tipo de mudanca foi. Um evento pode ser de mais de um tipo.
    situacao_julgamento is distinct from situacao_julgamento_anterior   as mudou_julgamento,
    situacao_candidatura is distinct from situacao_candidatura_anterior as mudou_situacao,
    sigla_partido is distinct from sigla_partido_anterior               as mudou_partido,
    nome_coligacao is distinct from nome_coligacao_anterior             as mudou_coligacao,
    nome_urna is distinct from nome_urna_anterior                       as mudou_nome_urna,
    coalesce(foi_substituido, false)
        and not coalesce(foi_substituido_anterior, false)               as virou_substituido,

    'Data da captura pelo pipeline, nao a data do ato do TSE.' as aviso_temporal,

    /*
      A candidatura ainda consta na ULTIMA publicacao do TSE?

      FALSE significa que ela existiu, foi capturada aqui, e depois DESAPARECEU da
      lista — registro cancelado, retirado, ou corrigido pelo TSE. Nao e' erro: e'
      exatamente o evento que este modelo existe para registrar, e que some sem
      rastro para quem so' le' a publicacao de hoje.

      Medido em 28/08/2026: 4 candidaturas (AC, GO, MS e outra), todas com foto no
      pacote de imagens e ausentes do `consulta_cand` do mesmo dia.

      A tela precisa dizer "esta candidatura nao consta mais na lista do TSE" em
      vez de exibi-la como se fosse atual.
    */
    atual.sk_candidatura is not null                                   as consta_na_lista_atual

from com_anterior
left join (
    select sk_candidatura from {{ ref('fct_candidatura') }}
) as atual using (sk_candidatura)
-- a versao 1 e' a primeira observacao, nao uma mudanca
where versao > 1
