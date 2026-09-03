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

# TETO DE TEMPO POR RECURSO, em segundos.
#
# So' o numero de tentativas nao limita nada: seis tentativas com timeout de 120s
# e backoff ate' 64s chegam a QUATORZE MINUTOS num unico arquivo. Em 30/08/2026
# a API da Camara caiu e o passo das proposicoes gastou 1h20 tentando dois
# arquivos - o dobro do que a carga inteira leva quando tudo funciona.
#
# Um teto e' mais preciso que reduzir tentativas: host que falha rapido gasta as
# seis em segundos e nao perde nada; host que demora para responder desiste no
# limite, em vez de multiplicar timeout por tentativa.
#
# Cinco minutos porque a decisao ja' esta' tomada mesmo: fonte que nao respondeu
# em cinco minutos vira aviso e a carga segue (ADR-022). Insistir mais so' adia
# o mesmo desfecho - e, desde que a atualizacao roda na maquina do usuario, adia
# com ele olhando a tela parada.
LIMITE_TOTAL = 300.0


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
    # Assinatura que o servidor deu na hora do download. E' com ela que o cache
    # e' REVALIDADO na execucao seguinte, em vez de aceito no escuro.
    # `None` nos manifestos antigos, e ai' a revalidacao simplesmente rebaixa.
    etag: str | None = None
    last_modified: str | None = None

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
        dados = json.loads(mf.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    # O `path` GRAVADO NAO VALE — vale `dest`.
    #
    # O manifesto guarda o caminho absoluto da maquina que baixou o arquivo. Esse
    # caminho nao sobrevive a nada: pasta renomeada, outro computador, ou o
    # workspace do GitHub Actions, que e' /home/runner/work/<repo>/<repo> e muda
    # quando o repositorio muda de nome. `dest` e' o caminho que o chamador pediu
    # AGORA, e a linha acima ja' confirmou que o arquivo esta' la'.
    #
    # Em 31/08/2026, renomear o projeto (ADR-026) fez o cache do CI restaurar
    # manifestos escritos sob /work/radar-brasil/, e a carga do RTN morreu com
    # FileNotFoundError apontando para um caminho que nao existia mais — tendo o
    # arquivo ao lado, no lugar certo.
    dados["path"] = str(dest)
    try:
        return Artifact(**dados)
    except TypeError:
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


def _mudou_no_servidor(url: str, cached: Artifact) -> bool | None:
    """A copia local ainda corresponde ao que o servidor serve?

    Devolve `True` (mudou), `False` (igual) ou `None` (nao deu para saber).

    POR QUE ISTO EXISTE

    O cache era CEGO: se o arquivo local batia com o proprio manifesto, `download`
    devolvia na hora, sem falar com o servidor. Junto com o cache de `data/raw`
    entre execucoes do GitHub Actions, isso produzia o pior resultado possivel
    para este projeto — o pacote do TSE baixado uma vez e NUNCA MAIS reconferido.

    Medido em 29/08/2026: a carga do dia rodou e gravou 20.769 linhas, mas
    `_extracted_at` continuava em 28/08 18:23 e o snapshot nao tinha nenhuma
    linha do dia. O pipeline diario estava recarregando o arquivo de ontem.

    Isso derruba a razao de o pipeline ser diario. O TSE publica sempre o ESTADO
    ATUAL, sem historico: a serie de alteracoes so' existe porque tiramos uma foto
    por dia, e no dia 28 foram 819 mudancas detectadas. Um dia sem reconferir e'
    um dia que nao volta.

    Um `HEAD` custa alguns bytes e responde a pergunta. Quando o servidor nao
    coopera — sem `ETag`, sem `Last-Modified`, ou o `HEAD` falha — devolve `None`
    e quem chama decide; aqui, decide rebaixar, porque o risco de perder uma
    mudanca e' maior que o custo de um download repetido.
    """
    req = urllib.request.Request(url, headers=BASE_HEADERS, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            etag = resp.headers.get("ETag")
            modificado = resp.headers.get("Last-Modified")
            tamanho = resp.headers.get("Content-Length")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("nao deu para revalidar %s (%s)", url, type(exc).__name__)
        return None

    # Tamanho diferente e' resposta definitiva, e nao depende de o servidor
    # mandar validador nenhum.
    if tamanho and tamanho.isdigit() and int(tamanho) != cached.size_bytes:
        return True
    if etag and cached.etag:
        return etag != cached.etag
    if modificado and cached.last_modified:
        return modificado != cached.last_modified
    # Sem validador guardado (manifesto antigo) nao da' para afirmar que esta'
    # igual. `None` faz rebaixar — o lado seguro do erro.
    return None if (etag or modificado) else False


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
    fallback: Artifact | None = None
    if cached and not force:
        intacto = (cached.size_bytes == dest.stat().st_size
                   and cached.sha256 == sha256_file(dest))
        if not intacto:
            log.warning("cache corrompido para %s — rebaixando", dest.name)
        elif dry_run:
            log.info("cache hit  %s (%s bytes)", dest.name, cached.size_bytes)
            return cached
        else:
            # O arquivo local esta' integro; a pergunta que falta e' se ele ainda
            # e' o que o servidor serve. Ver `_mudou_no_servidor`.
            mudou = _mudou_no_servidor(url, cached)
            if mudou is False:
                log.info("cache valido %s (%s bytes) — servidor confirma",
                         dest.name, cached.size_bytes)
                return cached
            log.info("cache desatualizado %s (%s) — rebaixando",
                     dest.name, "mudou no servidor" if mudou else "sem validador")
            # A COPIA LOCAL E' A REDE DE SEGURANCA, e nao lixo a descartar.
            #
            # Em 30/08/2026 a API da Camara ficou fora do ar. Os manifestos
            # antigos nao tinham validador guardado, entao a revalidacao devolveu
            # "nao sei" e mandou rebaixar — e o download falhou, derrubando um
            # pipeline que ANTES funcionava com o arquivo local intacto.
            #
            # A revalidacao existe para nao servir dado velho sem saber; ela nao
            # deve transformar indisponibilidade da fonte em perda do que ja'
            # temos. Se o redownload falhar por rede E a copia local estiver
            # integra, ela volta a valer, com aviso.
            fallback = cached

    if dry_run:
        log.info("[dry-run] baixaria %s -> %s", url, dest)
        return Artifact(url=url, path=str(dest), sha256="", size_bytes=0, extracted_at=utc_now())

    part = dest.with_suffix(dest.suffix + ".part")
    if force and part.exists():
        part.unlink()

    time.sleep(PAUSA_ENTRE_DOWNLOADS)

    last_error: Exception | None = None
    ok = False
    # Validadores que o servidor devolver: e' com eles que a proxima execucao
    # revalida este arquivo em vez de aceitar o cache no escuro.
    etag = modificado = None
    limite = time.monotonic() + LIMITE_TOTAL
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if time.monotonic() > limite:
            log.warning("%s: %.0fs sem sucesso — desistindo (teto de tempo)",
                        dest.name, LIMITE_TOTAL)
            break
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
                etag = resp.headers.get("ETag")
                modificado = resp.headers.get("Last-Modified")
                with part.open("ab" if offset else "wb") as fh:
                    while chunk := resp.read(CHUNK):
                        fh.write(chunk)
            ok = True
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            status = getattr(exc, "code", None)
            if status in (401, 404, 410):
                # Aqui a causa vai explicita para o objeto tambem: 401/404/410
                # devem mesmo ser permanentes, e agora isso e' afirmado pelo
                # codigo do HTTPError, nao por `causa` ter ficado None por
                # descuido.
                raise DownloadError(
                    f"{url} respondeu {status} — URL invalida", exc) from exc
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
        if fallback is not None:
            # Ver o comentario em `fallback = cached`, acima.
            log.warning(
                "%s nao pode ser rebaixado (%s) — seguindo com a copia local de %s",
                dest.name, type(last_error).__name__, fallback.extracted_at)
            return fallback
        # `causa=last_error` NAO E' DECORACAO — e' o que faz `transitoria`
        # funcionar. `from last_error` alimenta o traceback; quem guarda a causa
        # e' o construtor. Sem ela, `self.causa` fica None, `transitoria` avalia
        # None e devolve False, e TODO timeout de download virava erro
        # permanente: `executar` re-levantava, o processo saia com 1 e o job
        # inteiro caia.
        #
        # Foi o que aconteceu em 03/09/2026: um `<urlopen error timed out>` do
        # INEP derrubou a carga e pulou a publicacao do site. O mecanismo da
        # ADR-022 existia inteiro e estava desligado por um argumento que faltava
        # em UMA das tres chamadas — as de `get_texto` e `get_json` passavam.
        raise DownloadError(
            f"nao foi possivel baixar {url} apos {MAX_ATTEMPTS} tentativas: {last_error}",
            last_error,
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
        etag=etag,
        last_modified=modificado,
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
    limite = time.monotonic() + LIMITE_TOTAL
    for attempt in range(1, attempts + 1):
        if time.monotonic() > limite:
            log.warning("%s: teto de %.0fs atingido", url[:70], LIMITE_TOTAL)
            break
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
    limite = time.monotonic() + LIMITE_TOTAL
    for attempt in range(1, attempts + 1):
        if time.monotonic() > limite:
            log.warning("%s: teto de %.0fs atingido", url[:70], LIMITE_TOTAL)
            break
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
