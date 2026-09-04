{{
  config(
    materialized = 'table',
    cluster_by   = ['ano_eleicao', 'grupo_bem'],
    description  = 'Bens declarados por candidatura e tipo, agrupados pela tabela oficial (F-24).'
  )
}}

/*
  Grao: (sk_candidatura, cd_tipo_bem).

  A ficha mostrava "R$ 2.221.000, 10 itens" — um total e uma contagem, sem dizer
  do que o patrimonio e' feito. A fonte tem 76.724 itens so' em 2026, cada um com
  tipo e valor.

  ── A DESCRICAO DO BEM NAO ENTRA AQUI, E ISSO E' DELIBERADO ──

  `ds_bem` e' texto livre preenchido pelo candidato, e medido em 03/09/2026 sobre
  as 76.724 declaracoes de 2026 ele contem:

      endereco (rua, avenida, quadra, CEP, bairro)   5.218   6,8%
      CNPJ formatado                                 1.315   1,7%
      banco, agencia ou numero de conta                566   0,7%
      placa de veiculo                                 455   0,6%
      numero de porta                                  394   0,5%
      matricula de imovel                              217   0,3%
      CPF formatado                                    172   0,2%

  Um exemplo real: "DIREITOS POSSESSORIOS DO IMOVEL RESIDENCIAL NA RUA BEZERRA
  DA PALMA, 145, AFOGADOS, RECIFE/PE". Isso e' o ENDERECO RESIDENCIAL de uma
  pessoa real, e a Constituicao 0 proibe expor endereco de candidato.

  A protecao mais forte disponivel e' esta: o campo nao existe no mart. O que nao
  chega aqui nao pode chegar a' tela por descuido de quem escrever a proxima
  consulta — e nao depende de ninguem lembrar da regra.

  O TIPO, sim, entra: ele vem da tabela oficial de codigos, nao de texto livre.

  ── O AGRUPAMENTO VEM DA ESTRUTURA OFICIAL, NAO DO NOME ──

  `cd_tipo_bem` e' a tabela de Bens e Direitos da Receita Federal, que o TSE
  reusa, e ela ja' e' organizada por DEZENA:

      01-19  bens imoveis            41-49  aplicacoes e investimentos
      21-29  bens moveis             51-59  creditos e poupanca vinculada
      31-39  participacoes societarias  61-69  deposito a' vista e numerario
      71-79  fundos                  91-99  outros bens e direitos

  Classificar pela dezena e' ler a estrutura que a fonte ja' declara. Adivinhar
  pelo NOME seria repetir o erro que a L-20 custou caro: `RQI` parece
  "Requerimento de Informacao" e e' "Requerimento da Comissao de Servicos de
  Infraestrutura" (ADR-034).

  ── AUSENCIA NAO E' ZERO ──

  Candidatura que nao declarou bem nenhum simplesmente NAO TEM LINHA aqui. Ela
  nao vira uma linha de valor zero: 6.331 das 20.838 candidaturas exibidas de
  2026 nao declararam nada, e "R$ 0,00" afirmaria patrimonio nulo onde ha' apenas
  ausencia de declaracao (Regra 5).
*/

with itens as (

    select
        sk_candidatura,
        ano_eleicao,
        sq_candidato,
        cd_tipo_bem,
        tipo_bem,
        valor_bem
    from {{ ref('stg_tse__bens') }}
    where valor_bem is not null

)

select
    sk_candidatura,
    ano_eleicao,
    any_value(sq_candidato)                             as sq_candidato,
    cd_tipo_bem,
    any_value(tipo_bem)                                 as tipo_bem,

    -- A dezena do codigo E' o grupo, na tabela da Receita. `div` sobre o codigo
    -- devolve 0 para 01-03, 1 para 11-19, e assim por diante.
    case
        when cd_tipo_bem < 20 then 'imoveis'
        when cd_tipo_bem < 30 then 'moveis'
        when cd_tipo_bem < 40 then 'participacoes'
        when cd_tipo_bem < 50 then 'aplicacoes'
        when cd_tipo_bem < 60 then 'creditos'
        when cd_tipo_bem < 70 then 'dinheiro'
        when cd_tipo_bem < 80 then 'fundos'
        else 'outros'
    end                                                 as grupo_bem,

    count(*)                                            as qt_itens,
    sum(valor_bem)                                      as vl_total,
    max(valor_bem)                                      as vl_maior_item

from itens
group by sk_candidatura, ano_eleicao, cd_tipo_bem
