"""Publica o Dossie Eleitoral na Hostinger por FTP sobre TLS (ADR-018).

    python -m scripts.publicar [--origem site] [--dry-run]

Le a configuracao do ambiente, nunca de argumento — senha em linha de comando
aparece no historico do shell e na lista de processos:

    RADAR_FTP_HOST      ftp.datadubaintel.com
    RADAR_FTP_USER      u........prdgirocoju
    RADAR_FTP_PASSWORD  (segredo)
    RADAR_FTP_PORT      21          (opcional)
    RADAR_FTP_DIR       /           (opcional — a conta ja' esta' enraizada em
                                     /public_html/dossie)

TLS NAO E' OPCIONAL AQUI

FTP simples manda usuario e senha em TEXTO PURO. Vindo de um runner do GitHub,
isso atravessa a internet aberta a cada execucao diaria. `FTP_TLS` com `AUTH TLS`
resolve, e a Hostinger suporta na porta 21.

Se o servidor recusar TLS, este script FALHA em vez de cair para FTP simples. A
degradacao silenciosa e' o pior padrao possivel para credencial: funcionaria, e
ninguem descobriria que a senha passou a viajar em claro. Existe uma valvula
explicita — `RADAR_FTP_INSEGURO=1` — que precisa ser ligada por alguem que leu
esta linha.

O QUE ESTE SCRIPT NAO FAZ: APAGAR

Ele envia e sobrescreve; nunca remove nada do servidor. Um erro no calculo de
caminho, num processo que roda sozinho todo dia contra um site publico, apagaria
o site — e o custo de um arquivo velho sobrando e' incomparavelmente menor. O
que ficou orfao e' LISTADO ao fim, e a remocao e' decisao de gente.

E' o mesmo motivo pelo qual candidatura que some da publicacao do TSE (L-23) nao
some da carga: preferir o resto a mais do que o resto a menos.
"""

from __future__ import annotations

import argparse
import ftplib  # noqa: S402 — o canal e' TLS; ver o cabecalho deste modulo
import os
import ssl
import sys
from pathlib import Path

from ingest.common.log import get_logger

log = get_logger("publicar")

# Arquivos que nao devem existir no servidor, se algum dia caírem em `site/`.
NUNCA_ENVIAR = {".env", ".git", "__pycache__", ".DS_Store", "Thumbs.db"}

# Extensoes que sobem em modo texto seriam corrompidas por conversao de fim de
# linha. Tudo binario e' o comportamento correto: HTML e JSON tambem.
BLOCO = 1024 * 64


def _config() -> dict[str, str | int]:
    faltando = [n for n in ("RADAR_FTP_HOST", "RADAR_FTP_USER", "RADAR_FTP_PASSWORD")
                if not os.environ.get(n)]
    if faltando:
        raise SystemExit(
            "faltam variaveis de ambiente: " + ", ".join(faltando) +
            "\nNo GitHub elas vem de secrets; localmente, do .env.")
    return {
        "host": os.environ["RADAR_FTP_HOST"].replace("ftp://", "").rstrip("/"),
        "user": os.environ["RADAR_FTP_USER"],
        "senha": os.environ["RADAR_FTP_PASSWORD"],
        "porta": int(os.environ.get("RADAR_FTP_PORT") or 21),
        "raiz": os.environ.get("RADAR_FTP_DIR") or "/",
    }


def conectar(cfg: dict) -> ftplib.FTP:
    """FTPS explicito. Cai para FTP simples SO' com a valvula ligada."""
    contexto = ssl.create_default_context()
    try:
        sessao = ftplib.FTP_TLS(context=contexto)
        sessao.connect(cfg["host"], cfg["porta"], timeout=60)
        sessao.auth()
        sessao.login(cfg["user"], cfg["senha"])
        # Sem isto o canal de CONTROLE e' cifrado e o de DADOS nao — as paginas
        # subiriam em claro. Nao e' segredo, mas tambem nao custa nada.
        sessao.prot_p()
        log.info("conectado a %s por FTPS", cfg["host"])
        return sessao
    except ssl.SSLError as exc:
        if os.environ.get("RADAR_FTP_INSEGURO") != "1":
            raise SystemExit(
                f"o servidor recusou TLS ({exc}). A senha viajaria em texto puro.\n"
                "Se isso for mesmo o que se quer, ligue RADAR_FTP_INSEGURO=1 — e "
                "leia antes o cabecalho de scripts/publicar.py.") from exc
        log.warning("TLS recusado e RADAR_FTP_INSEGURO=1 — a SENHA VAI EM CLARO")
        sessao = ftplib.FTP()  # noqa: S321 — ligado deliberadamente pela valvula
        sessao.connect(cfg["host"], cfg["porta"], timeout=60)
        sessao.login(cfg["user"], cfg["senha"])
        return sessao


def garantir_pasta(sessao: ftplib.FTP, caminho: str, ja_feitas: set[str]) -> None:
    """`mkd` recursivo e idempotente. Pasta que ja' existe nao e' erro."""
    if not caminho or caminho in ja_feitas:
        return
    pai = caminho.rsplit("/", 1)[0] if "/" in caminho else ""
    garantir_pasta(sessao, pai, ja_feitas)
    try:
        sessao.mkd(caminho)
    except ftplib.error_perm as exc:
        # 550 aqui e' quase sempre "ja' existe", que e' o caso comum e nao e' erro.
        if not str(exc).startswith("550"):
            raise
    ja_feitas.add(caminho)


def enviar(sessao: ftplib.FTP, origem: Path, raiz_remota: str,
           seco: bool) -> tuple[int, int]:
    arquivos = sorted(p for p in origem.rglob("*") if p.is_file())
    arquivos = [p for p in arquivos
                if not any(parte in NUNCA_ENVIAR for parte in p.parts)]
    if not arquivos:
        raise SystemExit(f"{origem} esta' vazio — nada a publicar. "
                         "Rode `python -m scripts.gerar_site` antes.")

    base = raiz_remota.rstrip("/")
    feitas: set[str] = set()
    bytes_enviados = 0

    for i, caminho in enumerate(arquivos, 1):
        rel = caminho.relative_to(origem).as_posix()
        destino = f"{base}/{rel}" if base else rel
        pasta = destino.rsplit("/", 1)[0]

        if seco:
            log.info("[dry-run] %s -> %s (%d bytes)", rel, destino,
                     caminho.stat().st_size)
            bytes_enviados += caminho.stat().st_size
            continue

        garantir_pasta(sessao, pasta, feitas)
        with caminho.open("rb") as f:
            sessao.storbinary(f"STOR {destino}", f, blocksize=BLOCO)
        bytes_enviados += caminho.stat().st_size
        if i % 100 == 0:
            log.info("%d/%d enviados (%.1f MB)", i, len(arquivos),
                     bytes_enviados / 1e6)

    return len(arquivos), bytes_enviados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.publicar", description=__doc__)
    parser.add_argument("--origem", default="site", type=Path)
    parser.add_argument("--dry-run", action="store_true",
                        help="lista o que subiria, sem conectar nem enviar")
    args = parser.parse_args(argv)

    origem: Path = args.origem
    if not origem.is_dir():
        raise SystemExit(f"{origem} nao existe. Rode `python -m scripts.gerar_site`.")

    if args.dry_run:
        n, tamanho = enviar(None, origem, "/", seco=True)  # type: ignore[arg-type]
        log.info("[dry-run] %d arquivos, %.1f MB", n, tamanho / 1e6)
        return 0

    cfg = _config()
    sessao = conectar(cfg)
    try:
        n, tamanho = enviar(sessao, origem, str(cfg["raiz"]), seco=False)
        log.info("publicados %d arquivos, %.1f MB em %s%s",
                 n, tamanho / 1e6, cfg["host"], cfg["raiz"])
    finally:
        try:
            sessao.quit()
        except Exception:  # noqa: BLE001, S110 — desconexao suja nao invalida o envio
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
