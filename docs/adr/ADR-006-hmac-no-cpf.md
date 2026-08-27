# ADR-006 — HMAC-SHA256 com salt, nao SHA-256 puro

**Status:** Aceita · **Data:** 2026-08-27 · **Emenda a:** [ADR-005](ADR-005-chave-de-pessoa.md)

## Contexto
O SPEC secao 5 pede "SHA-256 do CPF". Mas o espaco de CPFs validos tem cerca de
10^11 elementos — pequeno o bastante para ser enumerado inteiro em poucos minutos
numa maquina comum. Um SHA-256 sem chave, portanto, **nao anonimiza**: quem tiver
a tabela consegue recuperar o CPF de cada candidato por forca bruta. Isso
devolveria exatamente o dado que a Constituicao secao 7 se comprometeu a nao expor.

## Decisao
`cpf_hash = HMAC-SHA256(chave = RADAR_CPF_SALT, mensagem = CPF)`.

Se `RADAR_CPF_SALT` nao estiver definido, a ingestao usa um salt publico
documentado e **avisa em log** que os hashes resultantes nao protegem o CPF.

## Motivo
- Sem a chave secreta, a enumeracao deixa de ser possivel.
- O fallback com salt publico preserva a Constituicao secao 4 (reprodutivel do
  zero por qualquer pessoa, sem segredo nenhum): quem so' quer reproduzir o
  pipeline consegue; quem vai publicar define o salt.
- O aviso em log impede que o modo inseguro passe despercebido.

## Consequencia
- **O salt faz parte do estado do projeto.** Trocar o salt invalida todo
  `id_pessoa` ja' materializado e exige `dbt run --full-refresh`.
- O salt e' segredo de infraestrutura (GitHub Secrets), nao de codigo.
