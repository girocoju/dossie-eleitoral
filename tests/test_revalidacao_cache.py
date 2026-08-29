"""O cache precisa PERGUNTAR ao servidor, nao supor.

O `download` devolvia a copia local sem falar com o servidor sempre que o arquivo
batia com o proprio manifesto. Junto com o cache de `data/raw` entre execucoes do
GitHub Actions, isso significava que o pacote do TSE era baixado uma vez e nunca
mais reconferido — e a razao de o pipeline ser diario e' exatamente reconferir.

Nada foi perdido quando isso foi descoberto (o TSE nao havia republicado desde
27/08/2026), mas o pipeline nao tinha como saber disso. Era sorte, nao garantia.
"""

from __future__ import annotations

import urllib.error
from unittest.mock import patch

import pytest

from ingest.common.http import Artifact, _mudou_no_servidor


def _cabecalhos(**kw):
    """Duble de resposta HTTP com os cabecalhos pedidos."""
    class Resp:
        headers = kw
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return Resp()


def _art(**kw) -> Artifact:
    base = {"url": "https://exemplo/x.zip", "path": "/tmp/x.zip",
            "sha256": "abc", "size_bytes": 1000, "extracted_at": "2026-08-29T00:00:00Z"}
    return Artifact(**{**base, **kw})


class TestMudouNoServidor:
    def _perguntar(self, art, **cabecalhos):
        with patch("urllib.request.urlopen", return_value=_cabecalhos(**cabecalhos)):
            return _mudou_no_servidor(art.url, art)

    def test_etag_igual_significa_cache_valido(self):
        art = _art(etag='"v1"')
        assert self._perguntar(art, ETag='"v1"', **{"Content-Length": "1000"}) is False

    def test_etag_diferente_significa_rebaixar(self):
        art = _art(etag='"v1"')
        assert self._perguntar(art, ETag='"v2"', **{"Content-Length": "1000"}) is True

    def test_tamanho_diferente_decide_sozinho(self):
        # Nao depende de validador nenhum: se o tamanho mudou, o arquivo mudou.
        art = _art(etag='"v1"')
        assert self._perguntar(art, ETag='"v1"', **{"Content-Length": "2000"}) is True

    def test_last_modified_quando_nao_ha_etag(self):
        art = _art(last_modified="Thu, 27 Aug 2026 15:35:38 GMT")
        assert self._perguntar(
            art, **{"Last-Modified": "Thu, 27 Aug 2026 15:35:38 GMT",
                    "Content-Length": "1000"}) is False
        assert self._perguntar(
            art, **{"Last-Modified": "Fri, 28 Aug 2026 09:34:19 GMT",
                    "Content-Length": "1000"}) is True

    def test_manifesto_antigo_sem_validador_nao_afirma_que_esta_igual(self):
        # E' o caso de todo manifesto gravado antes desta mudanca. Devolver
        # `False` ali seria continuar confiando no cache cego.
        art = _art()
        assert self._perguntar(art, ETag='"v1"', **{"Content-Length": "1000"}) is None

    def test_servidor_sem_validador_nenhum_aceita_o_cache(self):
        # Se o servidor nao manda ETag nem Last-Modified e o tamanho bate, nao ha'
        # mais nada a perguntar — rebaixar todo dia so' gastaria banda.
        art = _art()
        assert self._perguntar(art, **{"Content-Length": "1000"}) is False

    @pytest.mark.parametrize("erro", [
        urllib.error.URLError("fora do ar"),
        TimeoutError("timed out"),
        OSError("rede"),
    ])
    def test_falha_de_rede_nao_derruba_a_carga(self, erro):
        # Devolve `None`: quem chama rebaixa. Uma instabilidade no HEAD nao pode
        # transformar-se em erro fatal — ja' ha' retry no download em si.
        art = _art(etag='"v1"')
        with patch("urllib.request.urlopen", side_effect=erro):
            assert _mudou_no_servidor(art.url, art) is None


class TestManifesto:
    def test_artifact_aceita_manifesto_antigo(self):
        # Manifestos gravados antes desta mudanca nao tem os campos novos. Se o
        # dataclass exigisse, toda a base de cache viraria erro de carga.
        art = Artifact(url="u", path="p", sha256="s", size_bytes=1,
                       extracted_at="2026-08-29T00:00:00Z")
        assert art.etag is None
        assert art.last_modified is None
