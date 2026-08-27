{{
  config(
    materialized = 'table',
    cluster_by   = ['cod_cargo', 'sg_ue'],
    description  = 'Um mandato exercido por linha (SPEC 5). Base do modulo "Durante o mandato".'
  )
}}

/*
  Grao: um mandato = uma pessoa eleita para um cargo numa unidade eleitoral, com
  janela de anos.

  Le do STAGING e nao de `fct_candidatura` de proposito: `fct_candidatura` precisa
  de `fct_mandato` para derivar `is_reeleicao` (o TSE nao publica `ST_REELEICAO`
  preenchido antes da eleicao), e ler daqui para la' fecharia um ciclo. O criterio
  de "eleito" e' o mesmo dos dois lados — o macro `foi_eleito`.

  Janela de mandato (SPEC 5):
    - Presidente e Governador: ano_eleicao+1 .. ano_eleicao+4
    - Senador: 8 anos
    - Deputados: 4 anos
  A posse e' em 1o de janeiro (executivo) / 1o de fevereiro (legislativo) do ano
  seguinte; o projeto trabalha em grao ANUAL, entao a janela e' contada em anos
  inteiros e o primeiro ano de mandato e' sempre `ano_eleicao + 1`.

  `motivo_fim` so' e' preenchido quando a fonte informa cassacao. Fora isso fica
  `nao informado` — nao `fim regular` —, porque renuncia e morte no exercicio nao
  estao no `consulta_cand` e inventar o rotulo seria afirmar o que nao se sabe.
*/

with eleitos as (

    select
        c.sq_candidato,
        c.ano_eleicao,
        c.cod_cargo,
        c.sg_uf,
        c.sg_ue,
        c.nm_ue,
        c.sigla_partido,
        c.situacao_turno,
        c.situacao_cassacao,
        c.nome_urna,
        c.nome_completo
    from {{ ref('stg_tse__candidaturas') }} as c
    where c.foi_eleito
    qualify row_number() over (partition by c.sq_candidato order by c.nr_turno desc) = 1

),

com_pessoa as (

    select
        e.*,
        p.id_pessoa,
        p.link_confiavel
    from eleitos as e
    inner join {{ ref('dim_candidato') }} as p using (sq_candidato)
    -- sem chave de pessoa nao da' para afirmar de quem e' o mandato
    where p.id_pessoa is not null

),

com_janela as (

    select
        m.*,
        g.duracao_mandato_anos,
        g.titular,
        g.modulo_durante_mandato,
        g.esfera,
        m.ano_eleicao + 1                                        as ano_inicio,
        m.ano_eleicao + g.duracao_mandato_anos                    as ano_fim
    from com_pessoa as m
    inner join {{ ref('dim_cargo') }} as g using (cod_cargo)

)

select
    to_hex(sha256(concat(
        id_pessoa, '|', cast(cod_cargo as string), '|', sg_ue, '|', cast(ano_inicio as string)
    )))                                                          as sk_mandato,
    sq_candidato,
    id_pessoa,
    link_confiavel,
    nome_urna,
    nome_completo,
    cod_cargo,
    esfera,
    titular,
    modulo_durante_mandato,
    -- Presidente concorre na UE `BR`; os demais na sigla da UF
    case when cod_cargo = 1 then 'BR' else sg_uf end              as sg_uf,
    sg_ue,
    nm_ue,
    sigla_partido,
    ano_eleicao,
    ano_inicio,
    ano_fim,
    duracao_mandato_anos,
    situacao_turno,
    case
        when situacao_cassacao is not null
         and upper(situacao_cassacao) not in ('#NULO', 'NAO CASSADO')
            then 'cassacao'
        else 'nao informado'
    end                                                           as motivo_fim,
    -- mandato ainda em curso no momento da execucao do pipeline
    ano_fim >= extract(year from current_date())                  as em_curso
from com_janela
