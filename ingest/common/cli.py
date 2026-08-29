"""Saida padrao dos scripts de ingestao.

Um unico lugar decide o que o processo devolve ao sistema — e, por tabela, o que
o GitHub Actions faz com a falha.

    0    deu certo
    1    erro de verdade: bug, fonte que mudou de endereco, layout quebrado
    75   falha TRANSITORIA de rede (EX_TEMPFAIL, do sysexits.h)

O 75 existe por causa de 29/08/2026. Naquele dia um timeout de tres minutos da
API do SIDRA derrubou o job inteiro; horas depois, um timeout da API da Camara
derrubou de novo — e junto foram a carga do TSE do dia e a publicacao do site.
Uma indisponibilidade de API publica nao pode decidir se o dossie sai do ar.

O caminho obvio seria tornar tudo tolerante a falha. Seria pior: um bug meu, ou
uma fonte que mudou de URL, passaria como aviso e o dado pararia de atualizar sem
ninguem notar. Por isso a distincao e' feita AQUI, pela causa da excecao, e nao
por um `|| true` no YAML que nao sabe diferenciar as duas coisas.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ingest.common.http import DownloadError
from ingest.common.log import get_logger

log = get_logger("cli")

EX_REDE = 75


def executar(func: Callable[[Any], int], args: Any) -> int:
    """Roda o subcomando, traduzindo falha transitoria de rede em EX_REDE."""
    try:
        return int(func(args))
    except DownloadError as exc:
        if not exc.transitoria:
            # Fonte que mudou de endereco NAO e' instabilidade. Sobe como erro.
            raise
        log.error("falha transitoria de rede — nada foi carregado: %s", exc)
        return EX_REDE
