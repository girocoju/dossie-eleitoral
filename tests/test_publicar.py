"""Publicacao do dossie — ADR-018 / ADR-021. Testes puros, sem rede.

O foco e' a separacao entre "onde conectar" e "quem deve estar la'". Errar isso
nao quebra visivelmente: publicaria do mesmo jeito, com a senha exposta a quem
estivesse no caminho.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.publicar import NUNCA_ENVIAR, _config, _nomes_do_certificado, enviar

AMBIENTE = {
    "RADAR_FTP_HOST": "ftp.datadubaintel.com",
    "RADAR_FTP_USER": "usuario",
    "RADAR_FTP_PASSWORD": "senha",
}


@pytest.fixture
def limpo(monkeypatch):
    for chave in list(os.environ):
        if chave.startswith("RADAR_FTP"):
            monkeypatch.delenv(chave, raising=False)
    for chave, valor in AMBIENTE.items():
        monkeypatch.setenv(chave, valor)
    return monkeypatch


class TestConfig:
    def test_sem_nome_tls_o_padrao_e_o_host(self, limpo):
        # Comportamento padrao da stdlib: verificar contra quem se conectou.
        assert _config()["nome_tls"] == ""

    def test_nome_tls_separado_do_host(self, limpo):
        limpo.setenv("RADAR_FTP_TLS_NOME", "ftp.hstgr.io")
        cfg = _config()
        assert cfg["host"] == "ftp.datadubaintel.com"
        assert cfg["nome_tls"] == "ftp.hstgr.io"

    def test_esquema_no_host_e_removido(self, limpo):
        # A Hostinger entrega o host como `ftp://223.27.112.89` no painel, e
        # `connect()` nao aceita esquema.
        limpo.setenv("RADAR_FTP_HOST", "ftp://ftp.datadubaintel.com/")
        assert _config()["host"] == "ftp.datadubaintel.com"

    def test_falta_de_credencial_falha_dizendo_qual(self, limpo):
        limpo.delenv("RADAR_FTP_PASSWORD")
        with pytest.raises(SystemExit, match="RADAR_FTP_PASSWORD"):
            _config()


class TestNomesDoCertificado:
    def _der_com_sans(self, nomes: list[str]) -> bytes:
        corpo = b"".join(bytes([0x82, len(n)]) + n.encode() for n in nomes)
        return b"\x30\x82\x01\x00" + bytes([0x06, 0x03, 0x55, 0x1D, 0x11]) + \
            b"\x04\x20\x30\x1e" + corpo

    def test_le_os_nomes(self):
        # Os valores reais do servidor da Hostinger, medidos em 29/08/2026.
        assert _nomes_do_certificado(
            self._der_com_sans(["*.hstgr.io", "hstgr.io"])) == ["*.hstgr.io", "hstgr.io"]

    def test_certificado_sem_san_nao_explode(self):
        assert _nomes_do_certificado(b"\x30\x82\x01\x00qualquer coisa") == []

    def test_lixo_nao_explode(self):
        # O parser e' varredura, nao ASN.1 completo. Ele nunca decide nada de
        # seguranca, mas tambem nao pode derrubar o diagnostico.
        for entrada in (b"", b"\x82", b"\x82\xff", bytes(range(256))):
            assert isinstance(_nomes_do_certificado(entrada), list)


class TestEnvio:
    def test_dry_run_conta_o_que_subiria(self, tmp_path: Path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "index.html").write_text("<p>oi</p>", encoding="utf-8")
        (tmp_path / "sitemap.xml").write_text("<urlset/>", encoding="utf-8")
        n, tamanho = enviar(None, tmp_path, "/", seco=True)
        assert n == 2
        assert tamanho == 18

    def test_pasta_vazia_nao_publica(self, tmp_path: Path):
        # Publicar vazio substituiria o site por nada. Falha alto.
        with pytest.raises(SystemExit, match="vazio"):
            enviar(None, tmp_path, "/", seco=True)

    def test_arquivos_perigosos_ficam_de_fora(self, tmp_path: Path):
        (tmp_path / "index.html").write_text("ok", encoding="utf-8")
        (tmp_path / ".env").write_text("SENHA=1", encoding="utf-8")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"\x00")
        n, _ = enviar(None, tmp_path, "/", seco=True)
        assert n == 1, "so' o index.html devia subir"

    def test_nunca_enviar_cobre_o_env(self):
        assert ".env" in NUNCA_ENVIAR


class FTPFalso:
    """Grava o que teria sido feito, para conferir CAMINHOS sem tocar em rede.

    O bug de 29/08/2026 nao era detectavel por `--dry-run`: ele nao calcula
    pasta-pai nenhuma. So' um duble que registre os `mkd` pega.
    """

    def __init__(self):
        self.pastas: list[str] = []
        self.arquivos: list[str] = []
        self.removidos: list[str] = []

    def mkd(self, caminho):
        self.pastas.append(caminho)

    def rmd(self, caminho):
        self.removidos.append(caminho)
        raise OSError("nao existe")  # o caso normal

    def storbinary(self, cmd, f, blocksize=None):
        self.arquivos.append(cmd.removeprefix("STOR "))


class TestCaminhosRemotos:
    def _site(self, tmp_path: Path) -> Path:
        (tmp_path / "index.html").write_text("home", encoding="utf-8")
        (tmp_path / "sitemap.xml").write_text("<urlset/>", encoding="utf-8")
        (tmp_path / "candidato" / "fulano").mkdir(parents=True)
        (tmp_path / "candidato" / "fulano" / "index.html").write_text("x", encoding="utf-8")
        return tmp_path

    def test_arquivo_na_raiz_nao_vira_pasta(self, tmp_path: Path):
        # O BUG: `mkd("index.html")` criava um diretorio com o nome do arquivo, e
        # o `STOR` seguinte batia em `550 Not a regular file`. Quebrou a home do
        # dossie depois de 700 arquivos terem subido.
        ftp = FTPFalso()
        enviar(ftp, self._site(tmp_path), "/", seco=False)
        assert "index.html" not in ftp.pastas
        assert "sitemap.xml" not in ftp.pastas
        assert ftp.pastas == ["candidato", "candidato/fulano"]

    def test_todos_os_arquivos_chegam(self, tmp_path: Path):
        ftp = FTPFalso()
        enviar(ftp, self._site(tmp_path), "/", seco=False)
        assert sorted(ftp.arquivos) == [
            "candidato/fulano/index.html", "index.html", "sitemap.xml"]

    def test_raiz_configurada_prefixa_tudo(self, tmp_path: Path):
        ftp = FTPFalso()
        enviar(ftp, self._site(tmp_path), "/public_html/dossie", seco=False)
        assert "/public_html/dossie/index.html" in ftp.arquivos
        # A raiz de destino ja' existe: a conta de FTP esta' enraizada nela.
        # Tentar cria-la pediria `mkd /public_html`, fora do alcance da conta.
        assert not any(x.startswith("/public_html") and
                       "candidato" not in x for x in ftp.pastas)
        assert ftp.pastas == ["/public_html/dossie/candidato",
                              "/public_html/dossie/candidato/fulano"]

    def test_tenta_liberar_o_caminho_de_cada_arquivo(self, tmp_path: Path):
        # Auto-reparo: se um diretorio vazio estiver ocupando o lugar do arquivo,
        # ele sai. `RMD` recusa diretorio com conteudo, entao isso nao apaga dado.
        ftp = FTPFalso()
        enviar(ftp, self._site(tmp_path), "/", seco=False)
        assert "index.html" in ftp.removidos
