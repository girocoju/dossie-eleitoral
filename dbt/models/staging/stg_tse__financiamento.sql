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
    /*
      ── CPF DIGITADO NO CAMPO DO NOME ──

      Quem preenche a prestacao de contas as vezes escreve o CPF onde vai o
      nome. O TSE publica assim. Medido em 06/09/2026: 1 linha entre 82.710.

      A ingestao hasheia a COLUNA de CPF (ADR-020), mas nao tinha como saber que
      o numero viria noutro campo. Este `case` cobre o buraco: nome com a forma
      exata de CPF vira NULL, e `nome_era_cpf` registra que isso aconteceu.

      A doacao NAO e' descartada — valor, data e candidatura continuam, porque
      sao fato de interesse publico. O que sai e' so' o identificador da pessoa
      fisica, que o projeto nunca publica.

      Nao ha' validacao de digito verificador aqui de proposito. Onze digitos no
      lugar do nome ja' e' motivo suficiente para nao publicar: se for CPF, e'
      dado pessoal; se nao for, e' lixo que nao ajuda ninguem a identificar o
      doador. Nos dois casos a resposta certa e' a mesma.
    */
    case
        when regexp_contains({{ limpa('nome_doador') }}, r'^\d{11}$') then null
        else {{ limpa('nome_doador') }}
    end                                as nome_doador,
    regexp_contains({{ limpa('nome_doador') }}, r'^\d{11}$')
                                       as nome_era_cpf,
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
