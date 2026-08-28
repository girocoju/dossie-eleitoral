{{ config(materialized = 'view', description = 'Proposta de governo por candidatura majoritaria (S14, F-14).') }}

/*
  Grao: uma candidatura majoritaria consultada. Guarda a EXISTENCIA da proposta e
  o link para a pagina oficial — nunca o PDF (ADR-013).

  A ingestao reconsulta so' o que envelheceu, entao a mesma candidatura pode ter
  varias linhas ao longo do tempo. Fica a mais recente.
*/

select
    sk_candidatura,
    sq_candidato,
    {{ limpa('sg_ue') }}        as sg_ue,
    cod_cargo,
    tem_proposta                as tem_proposta_governo,
    n_arquivos                  as n_arquivos_proposta,
    {{ limpa('nome_arquivo') }} as nome_arquivo_proposta,
    {{ limpa('url_oficial') }}  as url_proposta_oficial,
    _extracted_at

from {{ source('raw_tse', 'propostas') }}
/*
  So' Presidente (1) e Governador (3). As linhas de Senador que a primeira carga
  trouxe ficam no `raw` como EVIDENCIA da medicao (0 de 318 com proposta), mas nao
  chegam ao mart: a Lei 9.504/97 nao pede proposta de senador, e deixa-lo aqui o
  faria aparecer como "nao consta" — uma acusacao de omissao inexistente.
*/
where cod_cargo in (1, 3)
qualify row_number() over (partition by sk_candidatura order by _extracted_at desc) = 1
