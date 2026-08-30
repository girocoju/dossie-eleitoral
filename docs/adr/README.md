# ADRs — registro de decisoes de arquitetura

Uma decisao por arquivo. Formato curto: contexto, decisao, consequencia.
A tabela-resumo vive em [SPEC.md](../../SPEC.md) secao 10 e tem de ser atualizada
junto com qualquer arquivo daqui.

| # | Decisao | Status |
|---|---|---|
| [ADR-001](ADR-001-power-bi.md) | Power BI em vez de Looker Studio | Substituida pela ADR-018 |
| [ADR-002](ADR-002-import-mode.md) | Import mode sobre tabelas agregadas | Aceita |
| [ADR-003](ADR-003-localizacao-bigquery.md) | Datasets do BigQuery em `US` | Aceita |
| [ADR-004](ADR-004-fonte-do-historico.md) | CSV do TSE como fonte unica, Base dos Dados so' para conferencia | Aceita |
| [ADR-005](ADR-005-chave-de-pessoa.md) | `cpf_hash` como chave de pessoa | Aceita |
| [ADR-006](ADR-006-hmac-no-cpf.md) | HMAC com salt, nao SHA-256 puro | Aceita |
| [ADR-007](ADR-007-hash-na-ingestao.md) | Hash na ingestao: CPF nunca chega ao warehouse | Aceita |
| [ADR-008](ADR-008-layout-declarativo.md) | Layout do TSE declarado em YAML, resolvido contra o header real | Aceita |
| [ADR-009](ADR-009-particionamento-sandbox.md) | Particao por inteiro e carga da tabela inteira (BigQuery sandbox) | Substituida pela ADR-010 |
| [ADR-010](ADR-010-particao-por-ano.md) | Volta da particao por ano com substituicao cirurgica | Aceita |
| [ADR-011](ADR-011-autenticacao-sem-chave.md) | GitHub Actions sem chave de service account (OIDC/WIF) | Aceita |
| [ADR-012](ADR-012-fotos-de-candidatos.md) | Fotos em bucket publico, nao no BigQuery | Aceita |
| [ADR-013](ADR-013-proposta-de-governo.md) | Proposta de governo: existencia + link, sem re-hospedar PDF | Aceita |
| [ADR-014](ADR-014-ponte-legislativo.md) | Ponte de identidade entre TSE e Camara/Senado | Aceita |
| [ADR-015](ADR-015-atividade-legislativa.md) | Atividade legislativa por classe, sem taxa de aprovacao | Aceita |
| [ADR-016](ADR-016-cadeia-tls-incompleta.md) | Intermediario TLS do INEP versionado no repositorio | Aceita |
| [ADR-017](ADR-017-orcamento-federal-pelo-rtn.md) | Orcamento federal pelo RTN, nao pela DCA | Aceita |
| [ADR-018](ADR-018-site-estatico-em-vez-de-bi.md) | Site estatico gerado do lake, em vez de ferramenta de BI | Aceita |
| [ADR-019](ADR-019-texto-integral-dos-planos.md) | Texto integral dos planos de governo, transcrito do PDF oficial | Aceita |
| [ADR-020](ADR-020-financiamento-de-campanha.md) | Financiamento de campanha, com o CPF do doador fora | Proposta |
| [ADR-021](ADR-021-tls-do-ftp-da-hostinger.md) | O nome que o certificado do FTP precisa cobrir | Aceita |
| [ADR-022](ADR-022-fonte-indisponivel.md) | Fonte indisponivel nao derruba a carga diaria | Aceita |
| [ADR-023](ADR-023-resultado-apurado-dos-votos.md) | Resultado apurado dos votos, onde o TSE nao publica | Aceita |
| [ADR-024](ADR-024-atividade-de-mandatos-anteriores.md) | Atividade legislativa de mandatos anteriores | Aceita |
| [ADR-025](ADR-025-plenario-e-chapas.md) | Votos, presenca e a chapa | Aceita |
