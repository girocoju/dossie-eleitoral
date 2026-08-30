"""A copia local e' rede de seguranca, nao lixo a descartar.

Em 30/08/2026 a API da Camara ficou fora do ar. Os manifestos antigos nao tinham
validador guardado, entao a revalidacao devolveu "nao sei" e mandou rebaixar — e
o download falhou seis vezes, derrubando um pipeline que ANTES daquela mudanca
funcionava normalmente com o arquivo local intacto.

A revalidacao existe para nao servir dado velho sem saber. Ela nao pode
transformar indisponibilidade da fonte em PERDA do que ja' esta' em disco.
"""

from __future__ import annotations

import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from ingest.common.http import Artifact, DownloadError, download, sha256_file


@pytest.fixture
def arquivo_em_cache(tmp_path: Path):
    """Um arquivo baixado antes, com manifesto SEM validador — o caso real."""
    import json
    dest = tmp_path / "proposicoes-2025.csv"
    dest.write_text("id;nome\n1;algo\n", encoding="utf-8")
    art = Artifact(url="https://exemplo/proposicoes-2025.csv", path=str(dest),
                   sha256=sha256_file(dest), size_bytes=dest.stat().st_size,
                   extracted_at="2026-08-29T12:00:00Z")
    # O manifesto vive ao lado, com sufixo `.manifest.json`.
    (tmp_path / "proposicoes-2025.csv.manifest.json").write_text(
        json.dumps({"url": art.url, "path": art.path, "sha256": art.sha256,
                    "size_bytes": art.size_bytes, "extracted_at": art.extracted_at}),
        encoding="utf-8")
    return dest, art


def test_fonte_fora_do_ar_nao_apaga_a_copia_local(arquivo_em_cache):
    dest, art = arquivo_em_cache
    conteudo = dest.read_bytes()

    # Revalidacao inconclusiva (manifesto antigo) e download que falha: e' o
    # cenario exato de 30/08/2026.
    with patch("ingest.common.http._mudou_no_servidor", return_value=None), \
         patch("ingest.common.http._open",
               side_effect=urllib.error.URLError("fora do ar")), \
         patch("ingest.common.http.time.sleep"):
        devolvido = download(art.url, dest)

    assert devolvido.sha256 == art.sha256, "devolveu outro arquivo"
    assert dest.read_bytes() == conteudo, "o arquivo local foi corrompido"
    assert devolvido.extracted_at == art.extracted_at, (
        "a data de extracao tem que ser a da copia, nao a de agora — a tela "
        "mostra essa data ao leitor")


def test_sem_copia_local_a_falha_continua_sendo_erro(tmp_path: Path):
    """Sem nada em disco nao ha' o que preservar: a falha sobe, e deve subir.

    `DownloadError` e' o que `executar` classifica como rede (ADR-022). Devolver
    silencio aqui faria a carga seguir sem dado nenhum.
    """
    with patch("ingest.common.http._open",
               side_effect=urllib.error.URLError("fora do ar")), \
         patch("ingest.common.http.time.sleep"), \
         pytest.raises(DownloadError):
        download("https://exemplo/novo.csv", tmp_path / "novo.csv")


def test_servidor_confirma_que_nao_mudou_e_nem_baixa(arquivo_em_cache):
    dest, art = arquivo_em_cache
    with patch("ingest.common.http._mudou_no_servidor", return_value=False), \
         patch("ingest.common.http._open") as abrir:
        devolvido = download(art.url, dest)
    abrir.assert_not_called()
    assert devolvido.sha256 == art.sha256


def test_servidor_diz_que_mudou_e_o_download_funciona(arquivo_em_cache):
    """O caminho normal continua normal: mudou, rebaixa, e o novo vale."""
    dest, art = arquivo_em_cache
    novo = b"id;nome\n1;outro\n2;mais\n"

    class Resp:
        status = 200
        headers = {"Content-Length": str(len(novo)), "ETag": '"v2"'}
        def __init__(self): self._d = [novo, b""]
        def read(self, *_a): return self._d.pop(0) if self._d else b""
        def __enter__(self): return self
        def __exit__(self, *_a): return False

    with patch("ingest.common.http._mudou_no_servidor", return_value=True), \
         patch("ingest.common.http._open", return_value=Resp()), \
         patch("ingest.common.http.time.sleep"):
        devolvido = download(art.url, dest)

    assert dest.read_bytes() == novo
    assert devolvido.sha256 != art.sha256
    assert devolvido.etag == '"v2"', "o validador novo tem que ficar no manifesto"
