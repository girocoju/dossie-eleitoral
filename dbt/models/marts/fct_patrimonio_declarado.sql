{{
  config(
    materialized = 'table',
    cluster_by   = ['ano_eleicao'],
    description  = 'Patrimonio declarado por pessoa e eleicao, para a serie da ficha (F-24).'
  )
}}

/*
  Grao: (id_pessoa, ano_eleicao).

  O TSE publica bens desde 2006. Uma pessoa que se candidatou em 2018, 2022 e
  2026 declarou tres vezes, e as tres declaracoes lado a lado dizem mais do que
  qualquer uma sozinha. Medido em 03/09/2026: 4.277 candidatos proporcionais de
  2026 tem tambem a declaracao de 2022.

  ── O QUE ESTE MODELO NAO CALCULA, DE PROPOSITO ──

  Nao ha' coluna de variacao, nem percentual, nem "enriqueceu". Tres motivos, e
  cada um sozinho ja' bastaria:

  1. O TSE pede valor de AQUISICAO, nao de mercado. Um imovel comprado em 2005 e
     declarado pelo preco de 2005 em todas as eleicoes seguintes. A diferenca
     entre dois anos mede compras e vendas tanto quanto qualquer outra coisa.

  2. Os valores sao NOMINAIS. R$ 500 mil em 2022 e R$ 550 mil em 2026 e' QUEDA em
     termos reais, e um "+10%" na tela afirmaria o contrario.

  3. E' declaracao do proprio candidato, nao apuracao de ninguem.

  A tela mostra as declaracoes e diz as tres coisas. Quem quiser concluir algo
  conclui com o dado a' vista — o site registra, nao avalia (Constituicao 0.1).

  ── SEM DECLARACAO NAO E' PATRIMONIO ZERO ──

  Ano em que a pessoa nao se candidatou, ou se candidatou e nao declarou bem
  nenhum, NAO gera linha. Preencher com zero desenharia uma queda a pico que
  nunca aconteceu (Regra 5).

  ── E 2006 SOMANDO ZERO TAMBEM NAO E' PATRIMONIO ZERO (L-27) ──

  Declaracao cujo total e' exatamente zero fica de fora. Medido em 03/09/2026:

      ano    candidaturas com bens    somam zero
      2006          19.263              6.699   (34,8%)
      2010          13.545                  0   ( 0,0%)
      2014          15.300                  0   ( 0,0%)
      2018          17.646                  1   ( 0,0%)
      2022          18.249                 26   ( 0,1%)
      2026          13.831                 14   ( 0,1%)

  Um terco de 2006 contra praticamente nada em todos os outros anos nao e' um
  fato sobre as pessoas de 2006 — e' um fato sobre o arquivo de 2006, que publica
  itens com valor zerado (10,3% dos itens daquele ano, contra ~0% nos demais).
  E' o segundo problema conhecido daquele arquivo; o primeiro e' a L-16, o
  desfecho da eleicao que ele nao publica.

  Deixar passar poria "R$ 0 em 2006" ao lado de "R$ 500 mil em 2026" na mesma
  ficha, e o leitor concluiria uma historia que o dado nao conta. Quem nao
  declarou nada nao tem linha; quem declarou zero tambem nao, porque zero aqui
  nao quer dizer zero.

  ── SO' CANDIDATURA EXIBIDA ──

  `e_registro_exibido` corta a reinscricao repetida do TSE. Sem o filtro, a mesma
  pessoa no mesmo ano teria duas linhas e o total sairia dobrado.
*/

with declaracoes as (

    select
        b.sk_candidatura,
        b.ano_eleicao,
        sum(b.valor_bem)                                as vl_total,
        count(*)                                        as qt_itens
    from {{ ref('stg_tse__bens') }} as b
    where b.valor_bem is not null
    group by b.sk_candidatura, b.ano_eleicao

),

com_pessoa as (

    select
        d.id_pessoa,
        d.ano_eleicao,
        d.sk_candidatura,
        d.cod_cargo,
        d.sg_uf,
        d.nome_urna,
        x.vl_total,
        x.qt_itens
    from declaracoes as x
    join {{ ref('dim_candidato') }} as d using (sk_candidatura)
    join {{ ref('fct_candidatura') }} as f using (sk_candidatura)
    where d.id_pessoa is not null
      and f.e_registro_exibido

)

select
    id_pessoa,
    ano_eleicao,

    -- Uma pessoa pode ter DUAS candidaturas exibidas no mesmo ano em casos
    -- raros (cargos distintos em eleicao suplementar). Somar os patrimonios
    -- seria contar o mesmo bem duas vezes; a declaracao e' a mesma pessoa, e a
    -- maior e' a completa.
    max(vl_total)                                       as vl_total_declarado,
    max(qt_itens)                                       as qt_itens,
    any_value(cod_cargo)                                as cod_cargo,
    any_value(sg_uf)                                    as sg_uf,
    any_value(nome_urna)                                as nome_urna,
    count(*)                                            as qt_candidaturas_no_ano

from com_pessoa
group by id_pessoa, ano_eleicao

-- Ver "2006 SOMANDO ZERO" no cabecalho: zero aqui nao quer dizer zero.
having max(vl_total) > 0
