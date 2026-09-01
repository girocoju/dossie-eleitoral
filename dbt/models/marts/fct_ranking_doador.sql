{{
  config(
    materialized = 'table',
    cluster_by   = ['doador_tipo', 'sg_uf_candidato'],
    description  = 'Quem financiou quem, em uma linha por doador x candidatura. Sem CPF (ADR-020).'
  )
}}

/*
  ===================================================================
  UMA LINHA POR DOADOR x CANDIDATURA. E' O PONTO DO MODELO.
  ===================================================================

  A pergunta que ele responde nao e' "quanto fulano doou", e sim "quanto fulano
  doou PARA CADA UM". Quem financia dois candidatos aparece duas vezes, com o
  valor de cada — somar as duas linhas apagaria exatamente a informacao que
  interessa, que e' a distribuicao do apoio.

  ── O que NAO entra ──

  CPF de pessoa fisica nunca foi ingerido (ADR-020): o TSE publica em texto puro,
  e o nome basta para prestar contas. CNPJ de empresa entra, porque identifica
  quem financia e e' de pessoa juridica.

  ── Autofinanciamento ──

  `e_o_proprio_candidato` marca as linhas em que o doador e' o proprio candidato.
  Elas ficam no ranking (decisao do dono do projeto em 01/09/2026), mas MARCADAS:
  dinheiro proprio e apoio externo sao coisas diferentes, e a tela precisa
  distinguir sem precisar de nota de rodape.

  ── Nada aqui e' juizo ──

  Ordenar por valor e' descrever, nao ranquear pessoa. A Constituicao 0.1 proibe
  ranking de "melhor/pior politico"; uma tabela de quanto cada um recebeu de cada
  financiador nao emite juizo nenhum sobre o candidato.
*/

with doacoes as (

    select
        sk_candidatura,
        sk_doador,
        nome_doador,
        doador_tipo,
        doador_cnpj,
        doador_uf,
        doador_ramo,
        vl_doado,
        qt_doacoes,
        e_o_proprio_candidato,
        ano_eleicao
    from {{ ref('fct_doador_candidatura') }}
    where ano_eleicao = 2026
      and vl_doado is not null
      and vl_doado > 0

),

candidatos as (

    select
        sk_candidatura,
        sq_candidato,
        nome_urna,
        sigla_partido,
        cod_cargo,
        sg_uf
    from {{ ref('dim_candidato') }}
    where ano_eleicao = 2026

)

select
    d.nome_doador,
    d.doador_tipo,
    d.doador_cnpj,
    d.doador_uf,
    d.doador_ramo,
    d.vl_doado,
    d.qt_doacoes,
    d.e_o_proprio_candidato,

    c.sq_candidato,
    c.nome_urna                                         as nome_candidato,
    c.sigla_partido                                     as partido_candidato,
    c.cod_cargo,
    c.sg_uf                                             as sg_uf_candidato,

    -- Quantas candidaturas DIFERENTES este doador financiou. E' o numero que
    -- transforma a tabela em leitura: um doador com 1 e' apoio; com 14, e' outra
    -- coisa — e a tela pode dizer isso sem que ninguem precise contar linhas.
    count(*) over (partition by d.sk_doador)            as candidaturas_do_doador,
    sum(d.vl_doado) over (partition by d.sk_doador)     as total_do_doador

from doacoes as d
inner join candidatos as c using (sk_candidatura)
