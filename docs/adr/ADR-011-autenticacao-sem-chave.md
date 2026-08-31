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

A confianca e' amarrada a um repositorio especifico em **DOIS lugares**, e os
dois precisam citar o mesmo repo. Isto e' a parte que se esquece:

**1. A condicao de atributo do provider** — quem pode *entrar* no pool:

    assertion.repository == 'girocoju/dossie-eleitoral'

**2. O binding da service account** — quem pode *personificar* a identidade:

    principalSet://iam.googleapis.com/projects/<numero>/locations/global/
      workloadIdentityPools/github/attribute.repository/girocoju/dossie-eleitoral

com papel `roles/iam.workloadIdentityUser`.

Um fork, ou qualquer outro repo, nao consegue assumir a identidade nem com o mesmo
provider configurado.

### Por que a distincao importa na pratica

Corrigir so' o item 1 produz uma falha que MENTE sobre onde esta' o problema. O
passo `google-github-actions/auth` **passa** — ele so' grava o arquivo de
credencial, sem trocar token nenhum. A execucao segue, e a quebra aparece varios
passos depois, na primeira chamada ao BigQuery:

    google.auth.exceptions.RefreshError: Unable to acquire impersonated
    credentials — Permission 'iam.serviceAccounts.getAccessToken' denied

Aconteceu em 31/08/2026, no rename do projeto (ADR-026): a condicao do provider
foi alargada para aceitar o nome novo, o binding da service account nao, e o
workflow falhou na "Ingestao TSE" com um traceback de 40 linhas que nao menciona
repositorio, WIF nem rename em lugar nenhum. **Autenticacao verde nao quer dizer
autorizacao concedida.**

## Motivo

- Nao existe segredo de longa duracao para vazar.
- O escopo e' o repositorio, nao a organizacao inteira.
- E' coerente com o resto do projeto: o ambiente local ja' usa ADC, e ADR-007
  recusou persistir CPF. Guardar uma chave permanente no CI contradiria isso.
- O alvo `ci` do dbt passou a usar `method: oauth`, o mesmo do `dev`. Um caminho
  de autenticacao a menos para manter.

## Consequencia

- O job exige `permissions: id-token: write` no workflow.
- A configuracao vive em variaveis do repositorio (`DOSSIE_WIF_PROVIDER`,
  `DOSSIE_WIF_SERVICE_ACCOUNT`), que nao sao segredos — sao identificadores.
- Trocar o repositorio de nome ou de dono quebra a confianca, e **os dois pontos
  acima** precisam ser atualizados — nao so' o provider. E' o preco de amarrar a
  confianca a um repo. Para renomear sem janela de indisponibilidade, aceite os
  dois nomes nos dois lugares primeiro, renomeie, e so' entao remova o antigo.
- `DOSSIE_CPF_SALT` continua sendo secret de verdade: e' a unica coisa que precisa
  ser secreta (ADR-006).
