# ADR-011 — GitHub Actions autentica sem chave de service account

**Status:** Aceita · **Data:** 2026-08-27

## Contexto

O pipeline precisa rodar diariamente no GitHub Actions ate' 04/10/2026 para
sustentar o snapshot das candidaturas. O caminho comum e' criar uma chave JSON de
service account e guarda-la como secret do repositorio.

Essa chave e' um segredo de longa duracao, sem expiracao, que fica em texto no
provedor de CI e no download que a gerou. Se vazar, da' acesso ao BigQuery ate'
alguem perceber e revoga-la.

## Decisao

Workload Identity Federation. O GitHub emite um token OIDC de curta duracao a cada
execucao; o GCP o troca por uma credencial temporaria da service account
a service account do pipeline. **Nenhuma chave e' criada em momento algum.**

A confianca e' amarrada a um repositorio especifico por condicao de atributo:

    assertion.repository == 'girocoju/radar-brasil'

Um fork, ou qualquer outro repo, nao consegue assumir a identidade nem com o mesmo
provider configurado.

## Motivo

- Nao existe segredo de longa duracao para vazar.
- O escopo e' o repositorio, nao a organizacao inteira.
- E' coerente com o resto do projeto: o ambiente local ja' usa ADC, e ADR-007
  recusou persistir CPF. Guardar uma chave permanente no CI contradiria isso.
- O alvo `ci` do dbt passou a usar `method: oauth`, o mesmo do `dev`. Um caminho
  de autenticacao a menos para manter.

## Consequencia

- O job exige `permissions: id-token: write` no workflow.
- A configuracao vive em variaveis do repositorio (`RADAR_WIF_PROVIDER`,
  `RADAR_WIF_SERVICE_ACCOUNT`), que nao sao segredos — sao identificadores.
- Trocar o repositorio de nome ou de dono quebra a condicao de atributo, e o
  provider precisa ser atualizado. E' o preco de amarrar a confianca a um repo.
- `RADAR_CPF_SALT` continua sendo secret de verdade: e' a unica coisa que precisa
  ser secreta (ADR-006).
