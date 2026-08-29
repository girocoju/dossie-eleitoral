"""Download idempotente com cache, hash e retomada.

Por que nao e' um `urlretrieve`:

* O CDN do TSE (`cdn.tse.jus.br`) tem um WAF que responde **403** para requisicao
  com cabecalho incompleto — nao basta o User-Agent. Medido em 27/08/2026, mesma
  URL, mesmo segundo: so' com UA -> 403; com o conjunto completo de cabecalhos que
  um navegador manda (`Accept`, `Accept-Language`, `Sec-Fetch-*`, `sec-ch-ua`,
  `Referer`) -> 206. Foi o que derrubou o primeiro pipeline no GitHub Actions, onde
  a PRIMEIRA requisicao ja' falhava — parecia bloqueio de IP de datacenter e era
  formato de requisicao.
* Os arquivos sao grandes; queda no meio nao pode obrigar a baixar tudo de novo,
  entao o download e' retomado com `Range: bytes=N-`.
* Constituicao §3/§4: todo arquivo baixado registra `sha256`, tamanho, URL e
  `_extracted_at` num manifesto versionavel — e' isso que torna a carga auditavel.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from ingest.common.log import get_logger

log = get_logger("http")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
# Conjunto completo, na ordem que um Chrome manda. Retirar qualquer um destes
# reintroduz o 403 — conferido item a item em 27/08/2026.
BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    # `identity` de proposito: os pacotes ja' sao .zip e uma camada extra de
    # compressao (br, sobretudo) chegaria aqui sem quem descomprima.
    "Accept-Encoding": "identity",
    "Referer": "https://dadosabertos.tse.jus.br/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Chromium";v="120", "Not(A:Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Connection": "close",
}

# Pausa entre downloads. O WAF do TSE reage a rajada, e o projeto nao tem pressa:
# sao poucos arquivos por execucao.
PAUSA_ENTRE_DOWNLOADS = 2.0

CHUNK = 1 << 20  # 1 MiB
GZIP_MAGIC = bytes([0x1F, 0x8B])
MAX_ATTEMPTS = 6
BACKOFF_BASE = 4.0  # segundos; 4, 8, 16, 32, 64, 128


class DownloadError(RuntimeError):
    """Falha ao obter um recurso, depois de esgotadas as tentativas.

    Carrega a causa para que quem chama possa separar duas coisas MUITO
    diferentes que antes chegavam iguais:

        transitoria   timeout, conexao recusada, 502, 503, 429
                      -> a fonte esta' de pe', so' nao respondeu agora

        permanente    404, 403, 410
                      -> a fonte MUDOU. Tratar como transitoria esconderia
                         justamente o caso em que o projeto quebrou de verdade,
                         e o dado pararia de atualizar sem ninguem notar.

    A distincao existe para o pipeline diario decidir entre "avisa e segue" e
    "para tudo". Sem ela, so' havia a escolha entre derrubar a carga inteira a
    cada instabilidade de API publica e engolir qualquer erro em silencio.
    """

    # Nem todo 5xx e' transitorio e nem todo 4xx e' permanente. Esta lista e' a
    # intersecao util: codigos em que tentar de novo amanha e' a resposta certa.
    TRANSITORIOS = frozenset({408, 425, 429, 500, 502, 503, 504})

    def __init__(self, mensagem: str, causa: BaseException | None = None):
        super().__init__(mensagem)
        self.causa = causa

    @property
    def transitoria(self) -> bool:
        c = self.causa
        # HTTPError E' subclasse de URLError, entao vem primeiro: invertida, a
        # ordem classificaria todo 404 como transitorio.
        if isinstance(c, urllib.error.HTTPError):
            return c.code in self.TRANSITORIOS
        return isinstance(c, (urllib.error.URLError, TimeoutError, OSError))


@dataclass(frozen=True)
class Artifact:
    """Um arquivo baixado, com a procedencia que vai junto para o BigQuery."""

    url: str
    path: str
    sha256: str
    size_bytes: int
    extracted_at: str

    @property
    def file(self) -> Path:
        return Path(self.path)


def utc_now() -> str:
    """Timestamp ISO-8601 UTC — vira a coluna `_extracted_at` (SPEC §3)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _manifest_path(dest: Path) -> Path:
    return dest.with_suffix(dest.suffix + ".manifest.json")


def _read_manifest(dest: Path) -> Artifact | None:
    mf = _manifest_path(dest)
    if not (mf.exists() and dest.exists()):
        return None
    try:
        return Artifact(**json.loads(mf.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError):
        return None


def _write_manifest(dest: Path, art: Artifact) -> None:
    _manifest_path(dest).write_text(
        json.dumps(asdict(art), indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Cadeias de certificado incompletas ──────────────────────────────────────
#
# Alguns servidores publicos servem o certificado da folha sem o intermediario.
# O navegador disfarca (busca o intermediario pela extensao AIA); o Python nao, e
# a conexao morre com CERTIFICATE_VERIFY_FAILED antes de qualquer HTTP.
#
# `download.inep.gov.br` (IDEB) e' o caso. Diagnostico de 28/08/2026:
#
#   folha         CN=*.inep.gov.br, valida
#   intermediario CN=RNP ICPEdu GR46 OV TLS CA 2025   <- NAO e' enviado
#   raiz          CN=GlobalSign Root R46              <- ja' esta' no certifi
#
# Ou seja: nao falta CA confiavel, falta um elo. O intermediario e' publico e
# esta' versionado em `certs/`. Nao e' segredo nem excecao de seguranca — a
# verificacao continua completa, so' recebe a peca que o servidor omitiu.
#
# Foi o que desfez o diagnostico anterior da L-05, que atribuia a falha a
# "bloqueio de rede". Nao era.
CADEIAS_INCOMPLETAS = {
    "download.inep.gov.br": "rnp-icpedu-gr46-ov-tls-ca-2025.pem",
}

_DIR_CERTS = Path(__file__).resolve().parents[2] / "certs"


@lru_cache(maxsize=8)
def _contexto(host: str) -> ssl.SSLContext | None:
    """Contexto TLS com o intermediario que falta, ou None para o padrao."""
    arquivo = CADEIAS_INCOMPLETAS.get(host)
    if not arquivo:
        return None
    caminho = _DIR_CERTS / arquivo
    if not caminho.exists():
        raise DownloadError(
            f"{host} precisa do intermediario {arquivo}, que nao esta' em {_DIR_CERTS}. "
            "Sem ele a conexao falha na verificacao do certificado, nao na rede."
        )
    # Contexto PADRAO (stdlib, sem certifi — o nucleo da ingestao nao tem
    # dependencia externa) mais o elo que falta. A raiz GlobalSign Root R46 ja'
    # vem da loja do sistema, no Windows e no Ubuntu do CI.
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cafile=str(caminho))
    return ctx


def _open(
    url: str,
    *,
    offset: int = 0,
    timeout: float = 120.0,
    aceita_gzip: bool = False,
    json_apenas: bool = False,
):
    headers = dict(BASE_HEADERS)
    if json_apenas:
        # A API da Camara devolve XML quando o Accept e' o de navegador.
        headers["Accept"] = "application/json"
    if aceita_gzip:
        headers["Accept-Encoding"] = "gzip, deflate"
    if offset:
        headers["Range"] = f"bytes={offset}-"
    req = urllib.request.Request(url, headers=headers, method="GET")
    host = urllib.parse.urlparse(url).hostname or ""
    return urllib.request.urlopen(req, timeout=timeout, context=_contexto(host))


def download(
    url: str,
    dest: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    expected_sha256: str | None = None,
) -> Artifact:
    """Baixa `url` para `dest` de forma idempotente e devolve o `Artifact`.

    Reexecutar sem `force` nao rebaixa nada: o manifesto e' conferido contra o
    sha256 do arquivo em disco. Isso e' o que faz `make run` ser barato de repetir.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    cached = _read_manifest(dest)
    if cached and not force:
        if cached.size_bytes == dest.stat().st_size and cached.sha256 == sha256_file(dest):
            log.info("cache hit  %s (%s bytes)", dest.name, cached.size_bytes)
            return cached
        log.warning("cache invalido para %s — rebaixando", dest.name)

    if dry_run:
        log.info("[dry-run] baixaria %s -> %s", url, dest)
        return Artifact(url=url, path=str(dest), sha256="", size_bytes=0, extracted_at=utc_now())

    part = dest.with_suffix(dest.suffix + ".part")
    if force and part.exists():
        part.unlink()

    time.sleep(PAUSA_ENTRE_DOWNLOADS)

    last_error: Exception | None = None
    ok = False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        offset = part.stat().st_size if part.exists() else 0
        try:
            with _open(url, offset=offset) as resp:
                if offset and resp.status != 206:
                    # servidor ignorou o Range: recomeca do zero
                    offset = 0
                    part.unlink(missing_ok=True)
                total = resp.headers.get("Content-Range") or resp.headers.get("Content-Length")
                log.info(
                    "baixando  %s (tentativa %d, offset %d, %s)", dest.name, attempt, offset, total
                )
                with part.open("ab" if offset else "wb") as fh:
                    while chunk := resp.read(CHUNK):
                        fh.write(chunk)
            ok = True
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            status = getattr(exc, "code", None)
            if status in (401, 404, 410):
                raise DownloadError(f"{url} respondeu {status} — URL invalida") from exc
            if attempt == MAX_ATTEMPTS:
                break
            wait = BACKOFF_BASE * (2 ** (attempt - 1))
            log.warning(
                "falha (%s) em %s — nova tentativa em %.0fs [%d/%d]",
                type(exc).__name__,
                dest.name,
                wait,
                attempt,
                MAX_ATTEMPTS,
            )
            time.sleep(wait)

    if not ok:
        if part.exists() and part.stat().st_size == 0:
            part.unlink(missing_ok=True)
        raise DownloadError(
            f"nao foi possivel baixar {url} apos {MAX_ATTEMPTS} tentativas: {last_error}"
        ) from last_error

    part.replace(dest)
    digest = sha256_file(dest)
    if expected_sha256 and digest != expected_sha256:
        raise DownloadError(
            f"sha256 divergente para {dest.name}: esperado {expected_sha256}, obtido {digest}"
        )

    art = Artifact(
        url=url,
        path=str(dest),
        sha256=digest,
        size_bytes=dest.stat().st_size,
        extracted_at=utc_now(),
    )
    _write_manifest(dest, art)
    log.info("ok        %s (%s bytes, sha256 %s...)", dest.name, art.size_bytes, digest[:12])
    return art


def _decode_body(raw: bytes, encoding: str | None) -> bytes:
    """Alguns endpoints do IBGE respondem gzip mesmo sem `Accept-Encoding`."""
    if raw[:2] == GZIP_MAGIC or (encoding or "").lower() == "gzip":
        return gzip.decompress(raw)
    if (encoding or "").lower() in {"deflate", "zlib"}:
        return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


def get_texto(url: str, *, timeout: float = 120.0, attempts: int = MAX_ATTEMPTS) -> str:
    """Busca uma pagina como texto, com o mesmo retry de `get_json`."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with _open(url, timeout=timeout, aceita_gzip=True) as resp:
                raw = _decode_body(resp.read(), resp.headers.get("Content-Encoding"))
            return raw.decode("utf-8", "replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(BACKOFF_BASE * attempt)
    raise DownloadError(f"nao foi possivel obter {url}: {last_error}", last_error)


def get_json(url: str, *, timeout: float = 120.0, attempts: int = MAX_ATTEMPTS):
    """GET + parse JSON com o mesmo backoff. Usado por SIDRA e Ipeadata.

    Diferente do download de arquivo, aqui gzip e' bem-vindo: as respostas do IBGE
    chegam a dezenas de MB de JSON e `_decode_body` sabe descomprimir.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with _open(url, timeout=timeout, aceita_gzip=True, json_apenas=True) as resp:
                raw = _decode_body(resp.read(), resp.headers.get("Content-Encoding"))
            return json.loads(raw.decode("utf-8-sig"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            wait = BACKOFF_BASE * (2 ** (attempt - 1))
            log.warning("falha em %s (%s) — retry em %.0fs", url, type(exc).__name__, wait)
            time.sleep(wait)
    raise DownloadError(f"nao foi possivel obter {url}: {last_error}", last_error) from last_error
