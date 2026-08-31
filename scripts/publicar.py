"""Publica o Dossie Eleitoral na Hostinger por FTP sobre TLS (ADR-018).

    python -m scripts.publicar [--origem site] [--dry-run]

Le a configuracao do ambiente, nunca de argumento — senha em linha de comando
aparece no historico do shell e na lista de processos:

    DOSSIE_FTP_HOST      ftp.datadubaintel.com
    DOSSIE_FTP_USER      u........prdgirocoju
    DOSSIE_FTP_PASSWORD  (segredo)
    DOSSIE_FTP_PORT      21          (opcional)
    DOSSIE_FTP_DIR       /           (opcional — a conta ja' esta' enraizada em
                                     /public_html/dossie)
    DOSSIE_FTP_TLS_NOME  ftp.hstgr.io  (opcional — ver abaixo)

TLS NAO E' OPCIONAL AQUI

FTP simples manda usuario e senha em TEXTO PURO. Vindo de um runner do GitHub,
isso atravessa a internet aberta a cada execucao diaria. `FTP_TLS` com `AUTH TLS`
resolve, e a Hostinger aceita na porta 21 — TLS 1.3, medido em 29/08/2026.

Nada aqui afrouxa a verificacao: `verify_mode` continua CERT_REQUIRED e
`check_hostname` continua True, no canal de controle e no de dados. Nao existe
`CERT_NONE` neste modulo.

    O NOME QUE O CERTIFICADO PRECISA COBRIR

A Hostinger apresenta um certificado Sectigo legitimo para `*.hstgr.io` — a
infraestrutura dela — e NAO para o apelido do cliente, `ftp.datadubaintel.com`.
Verificar o hostname contra o endereco de conexao falha, e falha com razao: o
certificado realmente nao cobre aquele nome.

Entao `DOSSIE_FTP_TLS_NOME` separa as duas coisas, que sempre foram duas:

    onde conectar          DOSSIE_FTP_HOST      ftp.datadubaintel.com
    quem deve estar la'    DOSSIE_FTP_TLS_NOME  ftp.hstgr.io

A verificacao segue completa — cadeia ate' uma CA publica, validade e hostname.
Muda apenas contra QUAL nome, e o nome passa a ser o verdadeiro. Quem sequestrasse
o DNS de `datadubaintel.com` precisaria de um certificado publicamente confiavel
para algum `*.hstgr.io` para se passar pelo servidor. Nao e' o mesmo que aceitar
qualquer certificado.

O que isto NAO prova: qual maquina da Hostinger atendeu. Prova que e' a
Hostinger — que e' a afirmacao verdadeira disponivel.

    POR QUE NAO FIXAR O CERTIFICADO

Seria o instinto, e o projeto tem precedente (ADR-016, a intermediaria do INEP no
repo). Aqui nao serve: o certificado medido expira em 01/09/2026, tres dias
depois de ter sido lido. Uma impressao digital fixada quebraria a publicacao na
primeira renovacao, num sabado, sem ninguem entender o motivo.

    A VALVULA

Se o servidor recusar TLS, este script FALHA em vez de cair para FTP simples. A
degradacao silenciosa e' o pior padrao possivel para credencial: funcionaria, e
ninguem descobriria que a senha passou a viajar em claro. Existe uma valvula
explicita — `DOSSIE_FTP_INSEGURO=1` — que precisa ser ligada por alguem que leu
esta linha.

O QUE ESTE SCRIPT NAO FAZ: APAGAR

Ele envia e sobrescreve. Um erro no calculo de caminho, num processo que roda
sozinho todo dia contra um site publico, apagaria o site — e o custo de um
arquivo velho sobrando e' incomparavelmente menor. Arquivo orfao fica onde esta',
e remove-lo e' decisao de gente.

A UNICA excecao esta' em `_liberar_caminho`: um diretorio VAZIO ocupando o lugar
exato de um arquivo que vai ser escrito. E' auto-reparo de um bug que este
proprio modulo cometeu, e nao consegue apagar conteudo — `RMD` recusa diretorio
nao-vazio.

E' o mesmo motivo pelo qual candidatura que some da publicacao do TSE (L-23) nao
some da carga: preferir o resto a mais do que o resto a menos.
"""

from __future__ import annotations

import argparse
import ftplib  # noqa: S402 — o canal e' TLS; ver o cabecalho deste modulo
import ssl
import sys
import time
from collections.abc import Callable
from pathlib import Path

from ingest.common.env import definida, env
from ingest.common.log import get_logger

log = get_logger("publicar")

# Arquivos que nao devem existir no servidor, se algum dia caírem em `site/`.
NUNCA_ENVIAR = {".env", ".git", "__pycache__", ".DS_Store", "Thumbs.db"}

# Extensoes que sobem em modo texto seriam corrompidas por conversao de fim de
# linha. Tudo binario e' o comportamento correto: HTML e JSON tambem.
BLOCO = 1024 * 64

# QUEDA DE CONEXAO NO MEIO DA PUBLICACAO NAO E' ERRO, E' INSTABILIDADE.
#
# Sao 738 arquivos por FTP numa sessao unica que fica aberta por volta de treze
# minutos. Em 31/08/2026 o servidor da Hostinger cortou a conexao no meio e a
# publicacao inteira morreu com ConnectionResetError — depois de ja' ter subido
# centenas de arquivos, deixando o site com metade das paginas novas e metade
# antigas. Sem retomada, o unico caminho e' recomecar do zero e torcer.
#
# A distincao e' a mesma do ADR-022: `error_perm` (5xx) e' problema de verdade —
# caminho errado, permissao negada — e deve falhar alto. Conexao cortada e
# `error_temp` (4xx) sao instabilidade: reconecta e continua do mesmo arquivo.
TENTATIVAS_POR_ARQUIVO = 4
ESPERA_BASE = 2.0          # segundos: 2, 4, 8
RECONEXOES_MAX = 40        # rede ruim tem limite; alem disso e' outra coisa

# `error_perm` fica DE FORA de proposito: e' a excecao que precisa subir.
TRANSITORIAS = (OSError, EOFError, ftplib.error_temp)


def _config() -> dict[str, str | int]:
    # `definida` e nao `os.environ`: o nome antigo `RADAR_FTP_*` ainda resolve
    # enquanto o .env e os Secrets nao forem renomeados. Checar so' o nome novo
    # aqui abortaria a publicacao com "faltam variaveis" tendo todas definidas.
    faltando = [n for n in ("DOSSIE_FTP_HOST", "DOSSIE_FTP_USER", "DOSSIE_FTP_PASSWORD")
                if not definida(n)]
    if faltando:
        raise SystemExit(
            "faltam variaveis de ambiente: " + ", ".join(faltando) +
            "\nNo GitHub elas vem de secrets; localmente, do .env.")
    return {
        "host": env("DOSSIE_FTP_HOST").replace("ftp://", "").rstrip("/"),
        "user": env("DOSSIE_FTP_USER"),
        "senha": env("DOSSIE_FTP_PASSWORD"),
        "porta": int(env("DOSSIE_FTP_PORT") or 21),
        "raiz": env("DOSSIE_FTP_DIR") or "/",
        # Vazio = verificar contra o proprio host de conexao, que e' o
        # comportamento padrao e o correto para servidor com certificado
        # no proprio nome.
        "nome_tls": (env("DOSSIE_FTP_TLS_NOME") or "").strip(),
    }


def conectar(cfg: dict) -> ftplib.FTP:
    """FTPS com verificacao completa. Cai para FTP simples SO' com a valvula."""
    # Padrao da stdlib: CERT_REQUIRED + check_hostname. Nao e' relaxado em
    # lugar nenhum deste modulo.
    contexto = ssl.create_default_context()
    nome_tls = cfg["nome_tls"] or cfg["host"]
    try:
        sessao = ftplib.FTP_TLS(context=contexto)
        sessao.connect(cfg["host"], cfg["porta"], timeout=60)
        # `FTP_TLS` verifica o certificado contra `self.host`, tanto no canal de
        # controle (`auth`) quanto no de dados (`ntransfercmd`). Trocar aqui e' o
        # que separa "onde conectar" de "quem deve estar la'": a conexao TCP ja'
        # foi feita e nao e' afetada, e `makepasv` usa o IP do peer.
        sessao.host = nome_tls
        sessao.auth()
        sessao.login(cfg["user"], cfg["senha"])
        # Sem isto o canal de CONTROLE e' cifrado e o de DADOS nao — as paginas
        # subiriam em claro. Nao e' segredo, mas tambem nao custa nada.
        sessao.prot_p()
        if nome_tls != cfg["host"]:
            log.info("conectado a %s, certificado verificado como %s",
                     cfg["host"], nome_tls)
        else:
            log.info("conectado a %s por FTPS", cfg["host"])
        return sessao

    except ssl.SSLCertVerificationError as exc:
        # NAO e' recusa de TLS: o servidor ofereceu, e o certificado e' que nao
        # confere. Diagnosticar errado manda a pessoa procurar no lugar errado —
        # foi exatamente o que a primeira versao deste modulo fez.
        raise SystemExit(
            f"o certificado de {cfg['host']} nao passou na verificacao contra o "
            f"nome '{nome_tls}':\n  {exc}\n\n"
            "Em hospedagem compartilhada isso costuma ser normal: o servidor tem "
            "certificado do PROVEDOR, nao do dominio do cliente. Veja qual nome "
            "ele cobre com\n\n    python -m scripts.publicar --certificado\n\n"
            "e informe esse nome em DOSSIE_FTP_TLS_NOME. A verificacao continua "
            "completa; muda so' contra qual nome.") from exc

    except ssl.SSLError as exc:
        if env("DOSSIE_FTP_INSEGURO") != "1":
            raise SystemExit(
                f"o servidor recusou TLS ({exc}). A senha viajaria em texto puro.\n"
                "Se isso for mesmo o que se quer, ligue DOSSIE_FTP_INSEGURO=1 — e "
                "leia antes o cabecalho de scripts/publicar.py.") from exc
        log.warning("TLS recusado e DOSSIE_FTP_INSEGURO=1 — a SENHA VAI EM CLARO")
        sessao = ftplib.FTP()  # noqa: S321 — ligado deliberadamente pela valvula
        sessao.connect(cfg["host"], cfg["porta"], timeout=60)
        sessao.login(cfg["user"], cfg["senha"])
        return sessao


# OID do subjectAltName (2.5.29.17) em DER. Achar a extensao e ler os nomes
# `dNSName` (tag 0x82) e' varredura suficiente para um DIAGNOSTICO — nao ha'
# decisao de seguranca apoiada neste parser, so' uma mensagem para gente ler.
_OID_SAN = bytes([0x06, 0x03, 0x55, 0x1D, 0x11])


def _nomes_do_certificado(der: bytes) -> list[str]:
    i = der.find(_OID_SAN)
    if i < 0:
        return []
    nomes: list[str] = []
    # Depois do OID vem (opcionalmente) o booleano `critical`, entao um OCTET
    # STRING que embrulha a SEQUENCE de GeneralName. Varrer os 400 bytes
    # seguintes atras de tags 0x82 acha os dNSName sem implementar ASN.1.
    trecho = der[i:i + 400]
    j = 0
    while j < len(trecho) - 2:
        if trecho[j] == 0x82:
            n = trecho[j + 1]
            if 0 < n < 100 and j + 2 + n <= len(trecho):
                try:
                    nome = trecho[j + 2:j + 2 + n].decode("ascii")
                except UnicodeDecodeError:
                    j += 1
                    continue
                if all(c.isalnum() or c in ".-*" for c in nome) and "." in nome:
                    nomes.append(nome)
                    j += 2 + n
                    continue
        j += 1
    return nomes


def cmd_certificado(cfg: dict) -> int:
    """Mostra que identidade o servidor apresenta, sem enviar credencial.

    O handshake aqui NAO verifica — e' o unico ponto do modulo em que isso
    acontece, e existe justamente para diagnosticar por que a verificacao de
    verdade falhou. Nenhuma senha e' enviada: para em `auth()`, antes do login.
    """
    import hashlib  # noqa: PLC0415

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # noqa: S323 — so' leitura, sem credencial

    sessao = ftplib.FTP_TLS(context=ctx)
    sessao.connect(cfg["host"], cfg["porta"], timeout=30)
    print(f"\n{cfg['host']}:{cfg['porta']}")
    print(f"  banner  : {sessao.getwelcome()}")
    sessao.auth()
    cifra = sessao.sock.cipher()
    der = sessao.sock.getpeercert(binary_form=True) or b""
    sessao.close()

    print(f"  TLS     : {cifra[1]} ({cifra[0]})")
    print(f"  sha256  : {hashlib.sha256(der).hexdigest()}")

    nomes = _nomes_do_certificado(der)
    if nomes:
        print(f"  cobre   : {', '.join(nomes)}")
        cobre_host = any(
            n == cfg["host"] or (n.startswith("*.")
                                 and cfg["host"].endswith(n[1:])
                                 and cfg["host"].count(".") == n.count("."))
            for n in nomes)
        if cobre_host:
            print(f"\n  O certificado JA' cobre {cfg['host']} — nao ha' o que "
                  "configurar.")
        else:
            sugerido = next((n.replace("*", "ftp") for n in nomes
                             if n.startswith("*.")), nomes[0])
            print(f"\n  NAO cobre {cfg['host']}. Para verificar contra a "
                  "identidade real:\n"
                  f"      DOSSIE_FTP_TLS_NOME={sugerido}")
    else:
        print("  cobre   : nao foi possivel ler os nomes do certificado.\n"
              "            Use `openssl s_client -starttls ftp -connect "
              f"{cfg['host']}:{cfg['porta']}`.")
    return 0


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


def _liberar_caminho(sessao: ftplib.FTP, destino: str) -> None:
    """Remove um DIRETORIO VAZIO que esteja ocupando o lugar de um arquivo.

    A versao anterior deste modulo criou `/index.html` como diretorio (ver o
    comentario em `enviar`). Enquanto ele existir, o `STOR` do index de verdade
    falha e a home do dossie fica quebrada — e nao ha' como consertar sem acesso
    manual ao FTP, que so' o dono da conta tem.

    E' a UNICA remocao que este modulo faz, e ela nao consegue apagar conteudo:
    `RMD` recusa diretorio nao-vazio. No pior caso a chamada falha e o envio
    segue exatamente como antes. Nada e' removido por estar "sobrando" — so' o
    que esta' impedindo um arquivo de existir.
    """
    try:
        sessao.rmd(destino)
    except ftplib.all_errors:
        return  # o normal: nao existe, ou e' arquivo, ou tem conteudo dentro
    log.warning("removido diretorio vazio que ocupava o lugar do arquivo %s",
                destino)


def enviar(sessao: ftplib.FTP, origem: Path, raiz_remota: str,
           seco: bool, reconectar: Callable[[], ftplib.FTP] | None = None,
           ) -> tuple[int, int]:
    arquivos = sorted(p for p in origem.rglob("*") if p.is_file())
    arquivos = [p for p in arquivos
                if not any(parte in NUNCA_ENVIAR for parte in p.parts)]
    if not arquivos:
        raise SystemExit(f"{origem} esta' vazio — nada a publicar. "
                         "Rode `python -m scripts.gerar_site` antes.")

    base = raiz_remota.rstrip("/")
    # A pasta de destino JA' EXISTE — a conta de FTP esta' enraizada nela. Marcar
    # ela e os ancestrais como "ja' feitos" evita um `mkd /public_html` inutil,
    # que tenta criar diretorio fora do alcance da conta e so' polui o log com
    # erro de permissao. Criar o destino nao e' tarefa deste script; se ele nao
    # existir, o primeiro `STOR` falha alto, que e' o certo.
    feitas: set[str] = set()
    if base:
        partes = base.split("/")
        for i in range(len(partes)):
            feitas.add("/".join(partes[:i + 1]))
    bytes_enviados = 0
    reconexoes = 0

    for i, caminho in enumerate(arquivos, 1):
        rel = caminho.relative_to(origem).as_posix()
        destino = f"{base}/{rel}" if base else rel
        # Arquivo na RAIZ nao tem pasta-pai. Sem o `if`, `rsplit` devolve o
        # proprio nome do arquivo e o script cria um DIRETORIO `index.html`,
        # onde o `STOR` seguinte bate com `550 Not a regular file`. Aconteceu
        # em 29/08/2026, depois de 700 arquivos subirem: todos estavam em
        # subpasta, e a raiz vem tarde na ordem alfabetica.
        pasta = destino.rsplit("/", 1)[0] if "/" in destino else ""

        if seco:
            log.info("[dry-run] %s -> %s (%d bytes)", rel, destino,
                     caminho.stat().st_size)
            bytes_enviados += caminho.stat().st_size
            continue

        for tentativa in range(1, TENTATIVAS_POR_ARQUIVO + 1):
            try:
                garantir_pasta(sessao, pasta, feitas)
                _liberar_caminho(sessao, destino)
                with caminho.open("rb") as f:
                    sessao.storbinary(f"STOR {destino}", f, blocksize=BLOCO)
                break
            except TRANSITORIAS as erro:
                if reconectar is None or tentativa == TENTATIVAS_POR_ARQUIVO:
                    raise
                reconexoes += 1
                if reconexoes > RECONEXOES_MAX:
                    raise SystemExit(
                        f"{reconexoes} reconexoes em uma publicacao — isso deixou "
                        "de ser instabilidade de rede. Verifique a conexao e o "
                        "servidor antes de tentar de novo.") from erro
                espera = ESPERA_BASE * 2 ** (tentativa - 1)
                log.warning("%s: %s — reconectando em %.0fs (tentativa %d/%d)",
                            rel, type(erro).__name__, espera, tentativa,
                            TENTATIVAS_POR_ARQUIVO)
                time.sleep(espera)
                # A pasta ja' criada continua criada do outro lado, entao
                # `feitas` segue valendo depois de reconectar.
                sessao = reconectar()
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
    parser.add_argument("--certificado", action="store_true",
                        help="mostra a identidade TLS do servidor e sai; "
                             "nao envia credencial")
    args = parser.parse_args(argv)

    if args.certificado:
        return cmd_certificado(_config())

    origem: Path = args.origem
    if not origem.is_dir():
        raise SystemExit(f"{origem} nao existe. Rode `python -m scripts.gerar_site`.")

    if args.dry_run:
        n, tamanho = enviar(None, origem, "/", seco=True)  # type: ignore[arg-type]
        log.info("[dry-run] %d arquivos, %.1f MB", n, tamanho / 1e6)
        return 0

    cfg = _config()
    # A sessao viva fica num dicionario porque `enviar` pode troca-la no meio do
    # caminho; o `finally` precisa fechar a ATUAL, nao a que morreu.
    viva: dict[str, ftplib.FTP] = {"sessao": conectar(cfg)}

    def reconectar() -> ftplib.FTP:
        try:
            viva["sessao"].close()
        except Exception:  # noqa: BLE001, S110 — ja' esta' morta; fechar e' cortesia
            pass
        viva["sessao"] = conectar(cfg)
        return viva["sessao"]

    try:
        n, tamanho = enviar(viva["sessao"], origem, str(cfg["raiz"]), seco=False,
                            reconectar=reconectar)
        log.info("publicados %d arquivos, %.1f MB em %s%s",
                 n, tamanho / 1e6, cfg["host"], cfg["raiz"])
    finally:
        try:
            viva["sessao"].quit()
        except Exception:  # noqa: BLE001, S110 — desconexao suja nao invalida o envio
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
