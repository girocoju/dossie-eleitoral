"""O caminho gravado no manifesto nao pode ser a fonte da verdade.

O manifesto guarda o caminho ABSOLUTO da maquina que baixou o arquivo. Esse
caminho nao sobrevive a pasta renomeada, a outro computador, nem ao workspace do
GitHub Actions — que e' /home/runner/work/<repo>/<repo> e muda quando o
repositorio muda de nome.

Em 31/08/2026 o rename do projeto (ADR-026) fez o cache do CI restaurar
manifestos escritos sob /work/radar-brasil/, e a carga do RTN morreu com
FileNotFoundError apontando para um caminho inexistente — tendo o arquivo ao
lado, no lugar certo.
"""

from __future__ import annotations

import json

from ingest.common.http import _manifest_path, _read_manifest, utc_now


def _semear(tmp_path, path_gravado: str):
    dest = tmp_path / "dado.csv"
    dest.write_text("a,b\n1,2\n", encoding="utf-8")
    _manifest_path(dest).write_text(json.dumps({
        "url": "https://exemplo.gov.br/dado.csv",
        "path": path_gravado,
        "sha256": "abc",
        "size_bytes": dest.stat().st_size,
        "extracted_at": utc_now(),
    }), encoding="utf-8")
    return dest


def test_caminho_de_outra_maquina_e_ignorado(tmp_path):
    dest = _semear(tmp_path, "/home/runner/work/radar-brasil/radar-brasil/data/dado.csv")
    art = _read_manifest(dest)
    assert art is not None
    assert art.file == dest, "tem que valer o destino pedido agora, nao o gravado"
    assert art.file.exists()


def test_caminho_de_pasta_renomeada_e_ignorado(tmp_path):
    dest = _semear(tmp_path, r"C:\Users\alguem\projeto-com-nome-antigo\data\dado.csv")
    art = _read_manifest(dest)
    assert art is not None and art.file == dest


def test_o_resto_do_manifesto_continua_valendo(tmp_path):
    """So' o `path` e' descartado — procedencia e revalidacao seguem intactas."""
    dest = _semear(tmp_path, "/caminho/que/nao/existe/dado.csv")
    art = _read_manifest(dest)
    assert art.url == "https://exemplo.gov.br/dado.csv"
    assert art.sha256 == "abc"
    assert art.size_bytes == dest.stat().st_size


def test_manifesto_sem_o_arquivo_ao_lado_nao_vale(tmp_path):
    dest = _semear(tmp_path, str(tmp_path / "dado.csv"))
    dest.unlink()
    assert _read_manifest(dest) is None, "sem o arquivo, nao ha' cache a aproveitar"
