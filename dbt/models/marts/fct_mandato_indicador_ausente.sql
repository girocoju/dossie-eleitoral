{{
  config(
    materialized = 'table',
    cluster_by   = ['cod_indicador', 'sg_uf'],
    description  = 'Por que um indicador NAO aparece na ficha de um mandato. A ausencia dita, em vez de silenciosa.'
  )
}}

/*
  ===================================================================
  A AUSENCIA PRECISA SER DITA, NAO APENAS RESPEITADA.
  ===================================================================

  A Regra 5 do projeto proibe preencher buraco de dado, e `fct_mandato_indicador`
  a cumpre: onde a serie nao alcanca a janela do mandato, o par simplesmente nao
  existe. Mas a ficha entao OMITE a linha sem dizer que omitiu — e quem le' nao
  tem como distinguir "nao ha' dado" de "o dado foi escondido" ou de "o site esta'
  incompleto".

  Em 01/09/2026 o proprio dono do projeto perguntou por que a ficha do Lula nao
  mostrava desemprego nos mandatos de 2003-2006 e 2007-2010. A resposta e' que a
  PNAD Continua comeca em 2012 (L-06). Se ele precisou perguntar, o leitor
  tambem precisaria — e a pagina de metodologia ainda afirmava que "a ficha fica
  sem o indicador e diz isso", coisa que a ficha nao fazia.

  Este modelo produz a lista do que falta e POR QUE falta, para a tela poder
  dizer. Nao inventa dado nenhum: so' nomeia a ausencia.

  ── Aplicabilidade ──

  A mesma regra do ADR-029: um indicador so' entra na conta se mede o ente que a
  pessoa chefiou. Nao faz sentido dizer a um presidente que "falta o orcamento do
  estado" — aquilo nunca caberia na ficha dele.

  ── A base da janela ──

  `fct_mandato_indicador` procura a ponta inicial no ano ANTERIOR a posse (a
  situacao herdada). Por isso a janela considerada aqui comeca em
  `ano_inicio - 1`: uma serie que so' comeca no ano da posse tambem nao produz
  variacao, e o motivo continua sendo alcance de serie.
*/

with mandatos as (

    select
        sk_mandato,
        id_pessoa,
        cod_cargo,
        sg_uf,
        nm_ue,
        ano_inicio,
        ano_fim,
        ano_inicio - 1                                      as base_ano
    from {{ ref('fct_mandato') }}
    where modulo_durante_mandato
      and titular

),

aplicaveis as (

    select
        m.*,
        i.cod_indicador,
        i.ente_medido
    from mandatos as m
    cross join {{ ref('dim_indicador') }} as i
    where i.ente_medido = 'territorio'
       or (i.ente_medido in ('governo_federal', 'economia_nacional') and m.cod_cargo = 1)
       or (i.ente_medido = 'governo_estadual' and m.cod_cargo = 3)

),

cobertura as (

    -- Alcance real da serie NA UNIDADE do mandato, nao no Brasil: uma serie pode
    -- existir nacionalmente e faltar para uma UF, e ai' o motivo e' outro.
    select
        cod_indicador,
        sg_uf,
        min(ano)                                            as serie_inicio,
        max(ano)                                            as serie_fim,
        count(*)                                            as anos_publicados
    from {{ ref('fct_indicador_uf_ano') }}
    where valor is not null
    group by cod_indicador, sg_uf

),

presentes as (

    select distinct sk_mandato, cod_indicador
    from {{ ref('fct_mandato_indicador') }}

),

ausentes as (

    select
        a.sk_mandato,
        a.id_pessoa,
        a.cod_cargo,
        a.sg_uf,
        a.nm_ue,
        a.ano_inicio,
        a.ano_fim,
        a.base_ano,
        a.cod_indicador,
        a.ente_medido,
        c.serie_inicio,
        c.serie_fim,
        -- quantos anos da serie caem DENTRO da janela considerada
        (
            select count(*)
            from {{ ref('fct_indicador_uf_ano') }} as f
            where f.cod_indicador = a.cod_indicador
              and f.sg_uf = a.sg_uf
              and f.valor is not null
              and f.ano between a.base_ano and a.ano_fim
        )                                                   as anos_na_janela
    from aplicaveis as a
    left join presentes as p
           on p.sk_mandato = a.sk_mandato
          and p.cod_indicador = a.cod_indicador
    left join cobertura as c
           on c.cod_indicador = a.cod_indicador
          and c.sg_uf = a.sg_uf
    where p.cod_indicador is null

)

select
    *,
    case
        -- A serie nao existe para esta unidade. Acontece com indicador que so'
        -- tem nivel nacional aparecendo em ficha estadual, e vice-versa.
        when serie_inicio is null                then 'sem_serie_para_a_unidade'
        -- Comeca depois do mandato inteiro: o caso do desemprego nos mandatos do
        -- Lula de 2003-2006 e 2007-2010 (PNAD Continua comeca em 2012).
        when serie_inicio > ano_fim              then 'serie_comeca_depois'
        -- Ja' tinha terminado antes de o mandato comecar.
        when serie_fim < base_ano                then 'serie_termina_antes'
        -- Alcanca a janela, mas com menos de dois pontos — e dois pontos e' o
        -- minimo para haver variacao. Serie decenal cai muito aqui.
        else                                          'serie_nao_cobre_a_janela'
    end                                                     as motivo
from ausentes
