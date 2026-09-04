"""Queda de conexao no meio da publicacao nao pode matar a publicacao inteira.

Sao 738 arquivos numa sessao FTP unica, aberta por volta de treze minutos. Em
31/08/2026 o servidor cortou a conexao no meio e tudo morreu com
ConnectionResetError, depois de centenas de arquivos ja' terem subido — o site
ficou com metade das paginas novas e metade antigas.

A distincao vem do ADR-022: `error_perm` (5xx) e' problema de verdade e sobe;
conexao cortada e `error_temp` (4xx) sao instabilidade e se resolvem
reconectando e continuando DO MESMO arquivo, sem reenviar o que ja' foi.
"""

from __future__ import annotations

import ftplib

import pytest

from scripts import publicar


class FTPFalso:
    """Sessao de mentira que registra o que subiu e pode quebrar sob encomenda."""

    def __init__(self, quebrar_em: list[int] | None = None,
                 erro: Exception | None = None) -> None:
        self.enviados: list[str] = []
        self.quebrar_em = set(quebrar_em or [])
        self.erro = erro or ConnectionResetError("conexao cortada")
        self.n = 0

    def storbinary(self, comando: str, arquivo, blocksize: int = 0) -> None:
        self.n += 1
        if self.n in self.quebrar_em:
            raise self.erro
        self.enviados.append(comando.removeprefix("STOR "))

    def cwd(self, caminho: str) -> None:
        return None

    def mkd(self, caminho: str) -> None:
        return None

    def rmd(self, caminho: str) -> None:
        # O caso normal: nao existe diretorio ocupando o lugar do arquivo.
        raise ftplib.error_perm("550 nao existe")

    def delete(self, caminho: str) -> None:
        return None

    def close(self) -> None:
        return None

    def quit(self) -> None:
        return None


def _site(tmp_path):
    origem = tmp_path / "site"
    origem.mkdir()
    for nome in ("index.html", "a.html", "b.html", "c.html"):
        (origem / nome).write_text("<html></html>", encoding="utf-8")
    return origem


def test_reconecta_e_continua_do_mesmo_arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(publicar, "ESPERA_BASE", 0.0)
    sessoes = [FTPFalso(quebrar_em=[2]), FTPFalso()]
    estado = {"i": 0}

    def reconectar():
        estado["i"] += 1
        return sessoes[estado["i"]]

    n, _ = publicar.enviar(sessoes[0], _site(tmp_path), "", seco=False,
                           reconectar=reconectar)

    assert n == 4
    assert estado["i"] == 1, "devia ter reconectado exatamente uma vez"
    subidos = sessoes[0].enviados + sessoes[1].enviados
    assert sorted(subidos) == ["a.html", "b.html", "c.html", "index.html"]
    assert len(subidos) == 4, f"nenhum arquivo pode subir duas vezes: {subidos}"


def test_erro_de_permissao_sobe_sem_reconectar(tmp_path, monkeypatch):
    """`error_perm` e' caminho errado ou permissao negada — tem que falhar alto."""
    monkeypatch.setattr(publicar, "ESPERA_BASE", 0.0)
    sessao = FTPFalso(quebrar_em=[1], erro=ftplib.error_perm("550 nao pode"))
    chamou = {"n": 0}

    def reconectar():
        chamou["n"] += 1
        return FTPFalso()

    with pytest.raises(ftplib.error_perm):
        publicar.enviar(sessao, _site(tmp_path), "", seco=False,
                        reconectar=reconectar)
    assert chamou["n"] == 0, "erro definitivo nao pode virar tentativa de reconexao"


def test_desiste_depois_do_limite_de_tentativas(tmp_path, monkeypatch):
    monkeypatch.setattr(publicar, "ESPERA_BASE", 0.0)

    def reconectar():
        return FTPFalso(quebrar_em=[1])

    with pytest.raises(ConnectionResetError):
        publicar.enviar(FTPFalso(quebrar_em=[1]), _site(tmp_path), "", seco=False,
                        reconectar=reconectar)


def test_sem_reconectar_o_erro_sobe_como_antes(tmp_path):
    """Quem chama sem `reconectar` (o dry-run, os testes antigos) nao muda."""
    with pytest.raises(ConnectionResetError):
        publicar.enviar(FTPFalso(quebrar_em=[1]), _site(tmp_path), "", seco=False)


# ── residuo de envio interrompido (ADR-045) ────────────────────────────────

class TestResiduoOculto:
    """O servidor grava o upload num oculto `.in.<nome>.` e so' renomeia no fim.

    Transferencia que morre no meio deixa o oculto, e o `STOR` seguinte no mesmo
    caminho responde 550. Como 550 e' `error_perm`, a publicacao inteira morria —
    foi o que aconteceu em 04/09/2026, depois de 6.200 arquivos.
    """

    ERRO = ("550 candidato/x-1/index.html: Temporary hidden file "
            "/candidato/x-1/.in.index.html. already exists")
    DESTINO = "candidato/x-1/index.html"

    def test_reconhece_o_residuo_e_devolve_caminho_RELATIVO(self):
        """O caminho e' DERIVADO do destino, nao copiado da mensagem.

        A mensagem do servidor traz o caminho ABSOLUTO
        (`/candidato/x-1/.in.index.html`), e o resto da sessao trabalha em
        caminho relativo a' raiz da conta FTP. O servidor resolve os dois de
        forma diferente: em 04/09/2026 o `STOR` dizia que o oculto existe e o
        `DELE` no caminho absoluto respondia "No such file or directory". A
        publicacao morreu com 11.800 de 20.906 ja' enviados.
        """
        from scripts.publicar import _residuo_de
        achado = _residuo_de(ftplib.error_perm(self.ERRO), self.DESTINO)
        assert achado == "candidato/x-1/.in.index.html"
        assert not achado.startswith("/"), "absoluto nao resolve nesta sessao"

    def test_arquivo_na_raiz_tambem_tem_residuo(self):
        from scripts.publicar import _residuo_de
        msg = ("550 index.html: Temporary hidden file /.in.index.html. "
               "already exists")
        assert _residuo_de(ftplib.error_perm(msg), "index.html") == ".in.index.html"

    def test_outro_550_continua_sendo_erro_de_verdade(self):
        """Caminho errado e permissao negada tambem sao 550, e precisam subir."""
        from scripts.publicar import _residuo_de
        for msg in ("550 Permission denied",
                    "550 /caminho/errado: No such file or directory",
                    "550 Not a regular file"):
            assert _residuo_de(ftplib.error_perm(msg), self.DESTINO) is None, msg

    def test_o_servidor_nao_escolhe_o_que_apagamos(self):
        """A mensagem serve para RECONHECER o caso; o endereco sai do destino.

        Nao importa o que o servidor mande — `/etc/passwd`, outra pasta, outro
        nome — o unico caminho que este modulo apaga e' o oculto do arquivo que
        ele mesmo esta' tentando escrever.
        """
        from scripts.publicar import _residuo_de
        for falso in ("/etc/passwd",
                      "/candidato/x-1/.in.outro.html.",
                      "/outra/pasta/.in.index.html."):
            msg = f"550 x: Temporary hidden file {falso} already exists"
            achado = _residuo_de(ftplib.error_perm(msg), self.DESTINO)
            assert achado == "candidato/x-1/.in.index.html", falso

    def test_um_arquivo_que_nao_limpa_nao_derruba_a_publicacao(self, tmp_path):
        """A versao anterior derrubava tudo. Em 04/09/2026 isso aconteceu com
        11.800 de 20.906 ja' enviados, por causa de UM arquivo.

        O arquivo fica FORA do manifesto, e por isso a proxima publicacao tenta
        de novo — perder uma pagina ate' amanha e' incomparavelmente melhor que
        perder a publicacao inteira hoje.
        """
        from scripts.publicar import enviar

        class SempreOcupado(FTPFalso):
            def storbinary(self, cmd, f, blocksize=8192):
                alvo = cmd.removeprefix("STOR ")
                if alvo == "b.html":
                    raise ftplib.error_perm(
                        f"550 {alvo}: Temporary hidden file /x/.in.index.html. "
                        "already exists")
                return super().storbinary(cmd, f, blocksize)

            def delete(self, caminho):
                raise ftplib.error_perm("550 No such file or directory")

        ftp = SempreOcupado()
        pendentes: list[str] = []
        n, _ = enviar(ftp, _site(tmp_path), "", seco=False,
                      nao_enviados=pendentes)
        assert pendentes == ["b.html"]
        assert {"index.html", "a.html", "c.html"} <= set(ftp.enviados)
        assert n == len(ftp.enviados)

    def test_remove_o_residuo_e_reenvia(self, tmp_path):
        """O arquivo tem de chegar, nao so' o erro sumir."""
        from scripts.publicar import enviar

        class ComResiduo(FTPFalso):
            def __init__(self):
                super().__init__()
                self.apagados = []
                self.primeira = True

            def storbinary(self, cmd, f, blocksize=8192):
                alvo = cmd.removeprefix("STOR ")
                if self.primeira and alvo.endswith("index.html"):
                    self.primeira = False
                    raise ftplib.error_perm(
                        f"550 {alvo}: Temporary hidden file "
                        f"/{alvo.rsplit('/', 1)[0]}/.in.index.html. already exists")
                return super().storbinary(cmd, f, blocksize)

            def delete(self, caminho):
                self.apagados.append(caminho)

        ftp = ComResiduo()
        enviar(ftp, _site(tmp_path), "", seco=False)
        assert ftp.apagados, "o oculto tinha de ser removido"
        assert any(x.endswith("index.html") for x in ftp.enviados), \
            "o arquivo tinha de chegar depois da limpeza"


def test_reconectar_falhando_nao_derruba_a_publicacao(monkeypatch):
    """Excecao levantada DENTRO de um `except` escapa do laco de retentativa.

    Em 04/09/2026 a publicacao morreu assim: `conectar()` deu TimeoutError
    (WinError 10060) enquanto tratava a queda anterior, e o erro passou por fora
    do `for tentativa`. Depois de centenas de reconexoes o servidor recusa por um
    tempo, e insistir com espera crescente atravessa isso.
    """
    from scripts import publicar

    monkeypatch.setattr(publicar.time, "sleep", lambda _: None)
    tentativas = {"n": 0}

    def conectar_instavel(cfg):
        tentativas["n"] += 1
        if tentativas["n"] < 3:
            raise TimeoutError("[WinError 10060] nao respondeu")
        return FTPFalso()

    monkeypatch.setattr(publicar, "conectar", conectar_instavel)

    class ArgsFalsos:
        origem = None

    viva = {"sessao": FTPFalso()}

    # Reproduz o `reconectar` de `main` com o mesmo contrato.
    def reconectar():
        for tentativa in range(1, publicar.TENTATIVAS_DE_RECONEXAO + 1):
            try:
                viva["sessao"] = publicar.conectar({})
                return viva["sessao"]
            except publicar.TRANSITORIAS:
                if tentativa == publicar.TENTATIVAS_DE_RECONEXAO:
                    raise
                publicar.time.sleep(1)
        raise AssertionError

    assert reconectar() is not None
    assert tentativas["n"] == 3, "tinha de insistir ate' conseguir"


def test_a_paciencia_da_reconexao_e_de_alguns_minutos():
    from scripts import publicar
    assert publicar.TENTATIVAS_DE_RECONEXAO >= 4
    espera = sum(publicar.ESPERA_BASE * 2 ** t
                 for t in range(1, publicar.TENTATIVAS_DE_RECONEXAO))
    assert espera >= 60, f"so' {espera}s de paciencia e' pouco para 20 mil arquivos"
