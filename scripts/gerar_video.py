"""Monta o video de divulgacao a partir dos quadros de `midia/`.

    python -m scripts.gerar_midia     # os quadros
    python -m scripts.gerar_video     # o video

Escreve `midia/dossie-eleitoral-<formato>.mp4`, um por proporcao.

── RITMO ──

A primeira versao usava fusao de 0,7s entre todos os cartoes, com 5s cada. Ficou
correta e sem graca: cadencia unica e' o que faz um video parecer apresentacao
de reuniao.

Aqui o corte varia. Cartao de texto fica pouco tempo — o olho le' uma frase curta
em menos de tres segundos e o resto e' espera. Captura de tela fica mais, porque
ela ROLA e a rolagem e' o que se esta' mostrando. E a transicao muda a cada
corte: deslize, corte circular, dissolucao. Nenhuma dura mais que meio segundo.

── AS CAPTURAS ROLAM SOZINHAS ──

Um quadro mais alto que o video nao e' encolhido: ele e' percorrido de cima para
baixo dentro do tempo do corte. E' o que mostra o site funcionando sem precisar
gravar tela.

── SEM TRILHA, DE PROPOSITO ──

O video sai MUDO. O LinkedIn nao tem biblioteca de musica, entao o audio precisa
vir embutido E licenciado; a do Instagram e' restrita para conta comercial.
Escolher a faixa e' de quem publica.

── H.264 E yuv420p ──

Nao e' o codec mais eficiente, e' o que TOCA em todo lugar. Sem `yuv420p` o
Windows Media Player e algumas visualizacoes do LinkedIn mostram tela preta — e o
erro so' aparece depois de publicado.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
from pathlib import Path

from ingest.common.log import get_logger

log = get_logger("video")

RAIZ = Path(__file__).resolve().parents[1]
MIDIA = RAIZ / "midia"
FPS = 30

# Cartao de texto: curto. Captura que rola: longa o bastante para a rolagem ser
# legivel. A capa e a chamada final respiram um pouco mais que o miolo.
SEG_CARTAO = 3.2
SEG_CAPTURA = 6.0
SEG_BORDA = 4.0          # capa

# Quadro que precisa de mais tempo que a regra geral. Grafico se le' devagar —
# ha' eixo, serie e legenda antes da frase — e a chamada final e' onde a pessoa
# decide se vai ao site.
SEG_POR_NOME = {
    "05-emendas": 6.4,
    "06-genero": 6.4,
    "10-cta": 8.0,
}

# Uma transicao diferente a cada corte, em ciclo. Todas curtas: transicao longa
# rouba o tempo da leitura.
TRANSICOES = [
    ("slideup", 0.45), ("smoothleft", 0.40), ("circleopen", 0.55),
    ("dissolve", 0.35), ("slideleft", 0.45), ("wipeup", 0.40),
    ("pixelize", 0.50), ("smoothright", 0.40), ("fadeblack", 0.45),
]


def _tamanho_png(caminho: Path) -> tuple[int, int]:
    """Largura e altura do cabecalho IHDR. Evita depender de Pillow."""
    cab = caminho.read_bytes()[:33]
    if cab[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{caminho.name} nao e' PNG")
    return struct.unpack(">II", cab[16:24])


def _ffmpeg() -> str:
    """O ffmpeg instalado pelo winget nao entra no PATH da sessao ja' aberta."""
    achado = shutil.which("ffmpeg") or os.environ.get("FFMPEG")
    if achado and Path(achado).exists():
        return achado
    pacotes = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for p in sorted(pacotes.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"), reverse=True):
        return str(p)
    raise SystemExit("ffmpeg nao encontrado — instale com: winget install Gyan.FFmpeg")


def montar(formato: str, larg: int, alt: int) -> Path | None:
    pasta = MIDIA / formato
    quadros = sorted(pasta.glob("*.png"))
    if len(quadros) < 2:
        log.warning("%s: %d quadros — rode antes `python -m scripts.gerar_midia`",
                    formato, len(quadros))
        return None

    entradas: list[str] = []
    filtros: list[str] = []
    duracoes: list[float] = []

    for i, q in enumerate(quadros):
        _, altura_png = _tamanho_png(q)
        rola = altura_png > alt * 1.15
        if q.stem in SEG_POR_NOME:
            d = SEG_POR_NOME[q.stem]
        elif rola:
            d = SEG_CAPTURA
        elif i in (0, len(quadros) - 1):
            d = SEG_BORDA
        else:
            d = SEG_CARTAO
        duracoes.append(d)
        entradas += ["-loop", "1", "-t", f"{d}", "-i", str(q)]

        if rola:
            # Percorre de cima para baixo e PARA um pouco antes do fim do corte,
            # para a imagem nao estar em movimento no instante da transicao.
            andar = max(d - 0.8, 0.1)
            y = (f"min(max(0\\,(ih-{alt})*(t/{andar}))\\,ih-{alt})")
            filtros.append(
                f"[{i}:v]fps={FPS},scale={larg}:-2,crop={larg}:{alt}:0:'{y}',"
                f"format=yuv420p,setsar=1[v{i}]")
        else:
            filtros.append(
                f"[{i}:v]fps={FPS},scale={larg}:{alt},format=yuv420p,setsar=1[v{i}]")

    # A fusao encadeia: o resultado de uma entra como lado esquerdo da seguinte.
    # Com duracoes DIFERENTES por corte, o deslocamento nao e' k*(D-T): e' a
    # soma do que ja' passou menos as sobreposicoes acumuladas.
    atual, acumulado = "v0", duracoes[0]
    for k in range(1, len(quadros)):
        nome, dur = TRANSICOES[(k - 1) % len(TRANSICOES)]
        offset = round(acumulado - dur, 3)
        filtros.append(
            f"[{atual}][v{k}]xfade=transition={nome}:duration={dur}:"
            f"offset={offset}[x{k}]")
        atual = f"x{k}"
        acumulado = acumulado - dur + duracoes[k]

    total = round(acumulado, 3)
    filtros.append(f"[{atual}]fade=t=in:st=0:d=0.4,"
                   f"fade=t=out:st={round(total - 0.6, 3)}:d=0.6[saida]")

    # O grafo vai INLINE. `-filter_complex_script` existia ate' o ffmpeg 7 e
    # foi removido no 9. Como os argumentos sao passados por LISTA, sem shell, a
    # virgula e as aspas do recorte chegam intactas — a barra invertida que
    # aparece na expressao e' escape do parser do proprio ffmpeg, nao do console.
    destino = MIDIA / f"dossie-eleitoral-{formato}.mp4"
    r = subprocess.run(
        [_ffmpeg(), "-y", *entradas,
         "-filter_complex", ";".join(filtros), "-map", "[saida]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         str(destino)],
        capture_output=True, text=True, errors="replace", timeout=1800)
    if r.returncode:
        # A mensagem util vem nas ultimas linhas; o resto da saida do ffmpeg e'
        # a lista de bibliotecas com que ele foi compilado.
        raise SystemExit("ffmpeg falhou:\n"
                         + "\n".join(r.stderr.strip().splitlines()[-8:]))
    log.info("%s — %d quadros, %.1fs, %d KB", destino.name, len(quadros),
             total, round(destino.stat().st_size / 1024))
    return destino


def main() -> None:
    if not MIDIA.is_dir():
        raise SystemExit("midia/ nao existe — rode antes: python -m scripts.gerar_midia")
    medidas = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
    for formato, (larg, alt) in medidas.items():
        if (MIDIA / formato).is_dir():
            montar(formato, larg, alt)


if __name__ == "__main__":
    main()
