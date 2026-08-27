# ADRs — registro de decisoes de arquitetura

Uma decisao por arquivo. Formato curto: contexto, decisao, consequencia.
A tabela-resumo vive em [SPEC.md](../../SPEC.md) secao 10 e tem de ser atualizada
junto com qualquer arquivo daqui.

| # | Decisao | Status |
|---|---|---|
| [ADR-001](ADR-001-power-bi.md) | Power BI em vez de Looker Studio | Aceita |
| [ADR-002](ADR-002-import-mode.md) | Import mode sobre tabelas agregadas | Aceita |
| [ADR-003](ADR-003-localizacao-bigquery.md) | Datasets do BigQuery em `US` | Aceita |
| [ADR-004](ADR-004-fonte-do-historico.md) | CSV do TSE como fonte unica, Base dos Dados so' para conferencia | Aceita |
| [ADR-005](ADR-005-chave-de-pessoa.md) | `cpf_hash` como chave de pessoa | Aceita |
| [ADR-006](ADR-006-hmac-no-cpf.md) | HMAC com salt, nao SHA-256 puro | Aceita |
| [ADR-007](ADR-007-hash-na-ingestao.md) | Hash na ingestao: CPF nunca chega ao warehouse | Aceita |
| [ADR-008](ADR-008-layout-declarativo.md) | Layout do TSE declarado em YAML, resolvido contra o header real | Aceita |
