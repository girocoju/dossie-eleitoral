"""Leitura de variaveis de ambiente com o nome antigo ainda aceito.

O projeto se chamava Radar Brasil e suas variaveis comecavam com `RADAR_`. Em
31/08/2026 tudo passou a se chamar Dossie Eleitoral (ADR-018 batizou o produto;
ADR-026 renomeou a infraestrutura), e o prefixo virou `DOSSIE_`.

RENOMEAR VARIAVEL DE AMBIENTE E' UMA MUDANCA COM VITIMA FORA DO REPO: o `.env` da
maquina do usuario e os Secrets do GitHub nao mudam quando o codigo muda. Um
`os.environ["DOSSIE_FTP_PASSWORD"]` publicado antes de o segredo existir derruba a
publicacao do site — e no caso do salt seria pior que derrubar: `id_pessoa` e'
HMAC do CPF com `RADAR_CPF_SALT` (ADR-006); se o nome novo nao resolvesse, o
codigo cairia no salt publico de fallback e REESCREVERIA todos os `id_pessoa` com
outra chave, quebrando em silencio a ponte de identidade entre legislaturas.
Silencio e' exatamente o que este projeto nao aceita.

Entao a troca e' gradual: le' `DOSSIE_`, aceita `RADAR_` e avisa uma vez por
variavel. Quando o `.env` e os Secrets estiverem renomeados, o aviso some sozinho
e este modulo pode ser reduzido a `os.environ.get`.
"""

from __future__ import annotations

import os

PREFIXO_NOVO = "DOSSIE_"
PREFIXO_ANTIGO = "RADAR_"

# Uma variavel avisa uma vez por processo. Uma carga toca `DOSSIE_GCP_PROJECT`
# dezenas de vezes; o aviso repetido viraria ruido e esconderia o resto do log.
_ja_avisadas: set[str] = set()


def _antigo(nome: str) -> str:
    return PREFIXO_ANTIGO + nome[len(PREFIXO_NOVO):]


def env(nome: str, default: str | None = None) -> str | None:
    """Valor de `nome`, ou do equivalente `RADAR_*`, ou o default."""
    valor = os.environ.get(nome)
    if valor is not None:
        return valor

    if nome.startswith(PREFIXO_NOVO):
        velho = _antigo(nome)
        valor = os.environ.get(velho)
        if valor is not None:
            if velho not in _ja_avisadas:
                _ja_avisadas.add(velho)
                # `print` e nao `log`: este modulo e' importado por `log.py`, que
                # o usa para descobrir o proprio nivel. Importar o logger aqui
                # fecharia um ciclo.
                print(f"[aviso] {velho} foi renomeada para {nome}. "
                      f"O nome antigo ainda funciona; renomeie quando puder.")
            return valor

    return default


def definida(nome: str) -> bool:
    """Se a variavel resolve por qualquer um dos dois nomes."""
    return env(nome) is not None
