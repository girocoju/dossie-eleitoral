# ADR-005 — `cpf_hash` como chave de pessoa entre eleicoes

**Status:** Aceita · **Data:** 2026-08-27 · **Origem:** SPEC secao 10

## Contexto
`SQ_CANDIDATO` e' unico por eleicao: a mesma pessoa recebe um numero diferente em
1998, 2014 e 2026. Sem uma chave de pessoa nao existe `fct_mandato`, nao existe
trajetoria e nao existe o modulo "Durante o mandato".

## Decisao
A chave de pessoa e' o hash do CPF. Quando o ano nao traz CPF, o fallback e' o
hash de `nome_completo` normalizado + `data_nascimento`, e a linha e' marcada com
`link_confiavel = false`. Sem nenhum dos dois, `id_pessoa` fica NULL e a
candidatura nao entra em `fct_mandato`.

## Motivo
- O CPF e' o unico identificador estavel entre pleitos.
- Hashear permite ligar sem expor (Constituicao secao 7).
- O fallback e' explicitamente rotulado porque homonimo com a mesma data de
  nascimento existe: quem le' a trajetoria precisa saber a diferenca.

## Consequencia
- Anos antigos com CPF ausente terao mais linhas com `link_confiavel = false`.
  A taxa e' medida pela analise `relatorio_vinculacao_pessoa` (T-205), nao estimada.
- Ver [ADR-006](ADR-006-hmac-no-cpf.md) para a forma do hash e
  [ADR-007](ADR-007-hash-na-ingestao.md) para onde ele e' calculado.
