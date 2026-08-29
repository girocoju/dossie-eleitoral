{{ config(materialized = 'view', description = 'Receitas declaradas de campanha, um registro por lancamento (S18, F-11).') }}

/*
  Grao: um lancamento de receita. 43.610 em 2026, sobre 7.722 candidaturas.

  O CPF DO DOADOR NAO CHEGA AQUI. `ingest/financiamento.py` hasheia pessoa fisica
  na origem e nunca grava o numero; CNPJ fica em claro porque identifica empresa,
  nao pessoa (ADR-020). Este modelo nao tem como reexpor o que nao foi carregado —
  e' de proposito: a garantia mora na ingestao, nao numa regra de SQL que alguem
  poderia contornar com um `select` diferente.

  `valor` ja' chega FLOAT64: a ingestao converte o decimal brasileiro em Python,
  entao aqui nao passa por `decimal_br`. E' a excecao no projeto e esta' anotada
  para nao parecer esquecimento.

  AUSENCIA NAO E' ZERO. Uma candidatura que nao aparece neste modelo NAO declarou
  zero — ela nao declarou nada, porque o prazo de prestacao vai ate' depois de
  04/10/2026. Nenhuma linha zerada e' fabricada para "completar" a base; a camada
  de apresentacao distingue os dois estados.
*/

select
    {{ sk_candidatura() }}              as sk_candidatura,
    ano_eleicao,
    sq_candidato,
    {{ limpa('sg_uf') }}               as sg_uf,
    {{ limpa('sg_ue') }}               as sg_ue,
    {{ inteiro('cod_cargo') }}         as cod_cargo,
    {{ limpa('sigla_partido') }}       as sigla_partido,

    sq_receita,
    {{ data_br('data_receita') }}      as data_receita,
    valor,
    {{ limpa('origem') }}              as origem_recurso,
    {{ limpa('fonte') }}               as fonte_recurso,
    {{ limpa('natureza') }}            as natureza_recurso,
    {{ limpa('especie') }}             as especie_recurso,

    -- ── doador ───────────────────────────────────────────────────────────────
    {{ limpa('nome_doador') }}         as nome_doador,
    {{ limpa('doador_cnpj') }}         as doador_cnpj,
    {{ limpa('doador_cpf_hash') }}     as doador_cpf_hash,
    doador_tipo,
    {{ limpa('doador_uf') }}           as doador_uf,
    {{ limpa('doador_cnae') }}         as doador_ramo,

    -- Identidade estavel do doador para agregacao: CNPJ quando empresa, hash
    -- quando pessoa. Nome sozinho nao serve — homonimia junta gente diferente.
    coalesce(
        {{ limpa('doador_cnpj') }},
        {{ limpa('doador_cpf_hash') }}
    )                                  as sk_doador,

    doador_sq_candidato,
    -- A FLAG VALE MAIS QUE O ROTULO DO TSE. Em 46 lancamentos rotulados
    -- `DS_ORIGEM_RECEITA = 'Recursos proprios'`, o `SQ_CANDIDATO_DOADOR` aponta
    -- para OUTRA candidatura, com outro nome — conferido em 28/08/2026. Marcar
    -- esses como recurso proprio diria, na ficha de uma pessoa, que o dinheiro de
    -- outra e' dela. A flag compara as chaves; o rotulo so' repete o que foi
    -- digitado na declaracao.
    e_autofinanciamento,
    _extracted_at

from {{ source('raw_tse', 'financiamento_receitas') }}
/*
  Lancamento zerado sem origem declarada: 1.273 registros em 2026, somando
  exatamente R$ 0,00. Nao sao buraco de dado — sao zeros reais do arquivo. Ficam
  no `raw` e saem daqui porque somar zero a uma origem nula so' criaria uma
  categoria "sem origem" vazia na tela.
*/
where valor is not null and valor <> 0
qualify row_number() over (partition by sq_receita order by _extracted_at desc) = 1
