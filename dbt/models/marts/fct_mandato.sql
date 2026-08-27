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

  Com DUAS correcoes que a fonte obrigou (conferido em 27/08/2026):

  1. **Eleicao suplementar.** O pacote de um ano contem suplementares realizadas
     depois: o de 2014 traz a do Amazonas (27/08/2017) e a do Tocantins
     (24/06/2018), ambas com ANO_ELEICAO=2014. Quem vence uma suplementar assume
     NO ANO DA ELEICAO e cumpre o que resta do mandato original. Tratar isso como
     `ano_eleicao + 1` daria a Amazonino Mendes uma janela de 2015 a 2018 — dois
     anos em que quem governava era outro. Como este modelo alimenta o
     "Durante o mandato", o erro apareceria na tela como indicador atribuido ao
     periodo errado.

  2. **Mandato interrompido.** Se houve suplementar para o mesmo cargo e unidade
     eleitoral dentro da janela, o mandato original terminou antes: seu `ano_fim`
     passa a ser o ano anterior a posse do sucessor, e `motivo_fim` vira
     `interrompido`. E' o unico caso de fim antecipado que a fonte permite deduzir
     sem inventar nada.

  `motivo_fim` so' e' preenchido quando a fonte informa cassacao. Fora isso fica
  `nao informado` — nao `fim regular` —, porque renuncia e morte no exercicio nao
  estao no `consulta_cand` e inventar o rotulo seria afirmar o que nao se sabe.
*/

with eleitos as (

    select
        c.sk_candidatura,
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
        c.nome_completo,
        c.is_eleicao_suplementar,
        c.ano_eleicao_efetivo
    from {{ ref('stg_tse__candidaturas') }} as c
    where c.foi_eleito
    qualify row_number() over (partition by c.sk_candidatura order by c.nr_turno desc) = 1

),

com_pessoa as (

    select
        e.*,
        p.id_pessoa,
        p.link_confiavel
    from eleitos as e
    inner join {{ ref('dim_candidato') }} as p using (sk_candidatura)
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
        -- suplementar: assume no proprio ano da eleicao. ordinaria: no ano seguinte.
        case
            when m.is_eleicao_suplementar then m.ano_eleicao_efetivo
            else m.ano_eleicao + 1
        end                                                       as ano_inicio,
        -- o fim e' sempre o do CICLO original, tanto para o titular quanto para
        -- quem completa o mandato via suplementar
        m.ano_eleicao + g.duracao_mandato_anos                    as ano_fim_previsto
    from com_pessoa as m
    inner join {{ ref('dim_cargo') }} as g using (cod_cargo)

),

-- primeiro ano de um sucessor eleito em suplementar, por cargo e UE
sucessao as (

    select
        cod_cargo,
        sg_ue,
        ano_eleicao,
        min(ano_inicio) as ano_inicio_sucessor
    from com_janela
    where is_eleicao_suplementar
    group by 1, 2, 3

),

ajustado as (

    select
        j.*,
        s.ano_inicio_sucessor,
        case
            when not j.is_eleicao_suplementar
             and s.ano_inicio_sucessor is not null
             and s.ano_inicio_sucessor > j.ano_inicio
                then s.ano_inicio_sucessor - 1
            else j.ano_fim_previsto
        end                                                       as ano_fim
    from com_janela as j
    left join sucessao as s
      on  s.cod_cargo   = j.cod_cargo
      and s.sg_ue       = j.sg_ue
      and s.ano_eleicao = j.ano_eleicao

)

select
    to_hex(sha256(concat(
        id_pessoa, '|', cast(cod_cargo as string), '|', sg_ue, '|', cast(ano_inicio as string)
    )))                                                          as sk_mandato,
    sk_candidatura,
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
    ano_eleicao_efetivo,
    is_eleicao_suplementar,
    ano_inicio,
    ano_fim,
    ano_fim - ano_inicio + 1                                      as anos_de_mandato,
    duracao_mandato_anos,
    situacao_turno,
    case
        when situacao_cassacao is not null
         and upper(situacao_cassacao) not in ('#NULO', 'NAO CASSADO')
            then 'cassacao'
        when ano_fim < ano_fim_previsto
            then 'interrompido'
        else 'nao informado'
    end                                                           as motivo_fim,
    -- mandato ainda em curso no momento da execucao do pipeline
    ano_fim >= extract(year from current_date())                  as em_curso
from ajustado
