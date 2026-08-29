{{ config(materialized = 'view', description = 'Despesas contratadas de campanha, um registro por lancamento (S18, F-11).') }}

/*
  Grao: uma despesa CONTRATADA. 54.019 lancamentos em 2026.

  CONTRATADA, NAO PAGA. O TSE publica os dois arquivos. "Paga" e' subconjunto de
  "contratada" e responde outra pergunta — quanto ja' saiu do caixa, nao quanto a
  campanha se comprometeu a gastar. Misturar os dois daria um numero que nao e'
  nenhum dos dois. Fica o compromisso assumido, que e' o que se compara com o
  limite legal de gasto.

  O CPF do fornecedor pessoa fisica passa pelo mesmo hash do doador (ADR-020):
  prestador de servico de campanha e' pessoa como qualquer outra.

  A CHAVE USA `sg_uf` PORQUE O ARQUIVO DE DESPESA NAO TRAZ `sg_ue`. Em eleicao
  geral os dois sao identicos — conferido nos 43.610 lancamentos de receita, onde
  ambos existem: zero divergencias. Em eleicao MUNICIPAL isso deixa de valer
  (`sg_ue` vira codigo de municipio) e esta substituicao passaria a fundir
  candidaturas. O teste `assert_despesa_casa_com_candidatura` guarda essa fronteira.
*/

select
    {{ sk_candidatura(sg_ue='sg_uf') }}     as sk_candidatura,
    ano_eleicao,
    sq_candidato,
    {{ limpa('sg_uf') }}                    as sg_uf,
    {{ inteiro('cod_cargo') }}              as cod_cargo,

    sq_despesa,
    {{ data_br('data_despesa') }}           as data_despesa,
    valor,
    {{ limpa('tipo_despesa') }}             as tipo_despesa,
    {{ limpa('descricao') }}                as descricao_despesa,

    {{ limpa('fornecedor_nome') }}          as nome_fornecedor,
    {{ limpa('fornecedor_cnpj') }}          as fornecedor_cnpj,
    {{ limpa('fornecedor_cpf_hash') }}      as fornecedor_cpf_hash,
    fornecedor_tipo,
    {{ limpa('fornecedor_uf') }}            as fornecedor_uf,
    _extracted_at

from {{ source('raw_tse', 'financiamento_despesas') }}
where valor is not null and valor <> 0
qualify row_number() over (partition by sq_despesa order by _extracted_at desc) = 1
