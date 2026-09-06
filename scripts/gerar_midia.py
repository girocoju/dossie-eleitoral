"""Quadros para o video de divulgacao, em vertical e horizontal.

    python -m scripts.gerar_midia

Escreve PNGs em `midia/`, prontos para montar em qualquer editor. Nao monta o
video: aqui nao ha' ffmpeg, e montagem com trilha e transicao e' trabalho de
editor, nao de script.

── POR QUE QUADROS DESENHADOS, E NAO CAPTURAS DE TELA ──

Captura de um site de desktop dentro de um quadro 9x16 fica com tarja preta em
cima e embaixo, ou cortada. Os quadros aqui usam a MESMA folha de estilo do site
— mesma paleta, mesma tipografia — e sao compostos para cada proporcao. O
resultado parece intencional, e nao um print esticado.

Os numeros vem de `data/relatorio/dados.json`, o mesmo arquivo que alimenta o
relatorio em PDF. Nenhum numero e' digitado aqui.

── O QUE NAO ENTRA NOS QUADROS ──

Nenhuma ficha individual, nenhum rosto, nenhum nome de candidato. O projeto vale
por nao destacar ninguem, e uma peca de divulgacao que mostra a ficha de fulano
sera' lida como destaque a fulano — em ano eleitoral, a intencao nao protege.
O argumento forte nao e' "veja a ficha do fulano": e' a escala e o rigor.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ingest.common.log import get_logger
from scripts.relatorio.graficos import ACENTO, OK, barras, linhas

log = get_logger("midia")

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "data" / "relatorio" / "dados.json"
SAIDA = RAIZ / "midia"
TMP = RAIZ / "data" / "midia"

# 9x16 para Reels e Stories; 16x9 para o feed do LinkedIn e YouTube.
FORMATOS = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}

CSS = """
*{box-sizing:border-box;margin:0}
html,body{width:100%;height:100%}
body{background:#07172C;color:#EAF1FA;
  font-family:Calibri,Carlito,"Segoe UI",Arial,sans-serif;
  display:flex;flex-direction:column;justify-content:var(--just);
  padding:var(--pad);position:relative;overflow:hidden}
/* Um brilho fraco no canto, para o fundo nao ser um retangulo chapado. Fica
   atras de tudo e nao carrega informacao nenhuma. */
body::after{content:"";position:absolute;right:-18%;top:-12%;
  width:70%;aspect-ratio:1;border-radius:50%;
  background:radial-gradient(circle,rgba(25,195,214,.13),transparent 68%);
  pointer-events:none}
.miolo{position:relative;z-index:1;max-width:var(--col)}
.faixa{position:absolute;top:0;left:0;right:0;height:var(--faixa);background:#19C3D6}
.selo{position:absolute;bottom:var(--pad);left:var(--pad);
  font-family:ui-monospace,Consolas,monospace;font-size:var(--selo);
  letter-spacing:.2em;text-transform:uppercase;color:#7E90AB}
.url{position:absolute;bottom:var(--pad);right:var(--pad);
  font-family:ui-monospace,Consolas,monospace;font-size:var(--selo);color:#19C3D6}
h1{font-size:var(--h1);line-height:1.03;letter-spacing:-.015em;font-weight:700}
h1 em{font-style:normal;color:#19C3D6}
p{font-size:var(--p);line-height:1.35;color:#AEBFD6;margin-top:var(--gap)}
.numero{font-size:var(--num);font-weight:700;line-height:.95;color:#19C3D6;
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.rotulo{font-size:var(--p);color:#EAF1FA;margin-top:var(--gap);line-height:1.28}
.nota{font-size:var(--nota);color:#7E90AB;margin-top:calc(var(--gap) / 1.5);
  line-height:1.45;max-width:34ch}
.titulo{font-size:var(--p);font-weight:700;color:#EAF1FA;margin-bottom:var(--gap)}
.grafico + .nota,.titulo{max-width:none}
/* O SVG do relatorio nasce com tinta escura, para papel branco. Aqui o fundo e'
   escuro: `invert(1) hue-rotate(180deg)` troca claro por escuro preservando o
   matiz das cores de serie, em vez de repintar cada elemento a mao. */
/* PAINEL BRANCO PARA O GRAFICO.
   O gerador de SVG e' o do relatorio em PDF: tinta escura sobre papel branco.
   A versao anterior o jogava no fundo escuro e invertia as cores por filtro —
   funcionava, e deixava o eixo cinza-sobre-azul, no limite da leitura. Num
   painel branco ele aparece como foi desenhado, com o contraste que ja' tinha
   sido pensado para ele. */
.grafico{background:#FFF;border-radius:calc(var(--gap) / 2);
  padding:calc(var(--gap) * .9) calc(var(--gap) * .8);margin-top:var(--gap)}
.grafico svg{width:100%;max-width:none;height:auto;display:block}
/* Caixa da chamada final: parece um botao sem fingir ser clicavel num video. */
.cta{display:inline-block;margin-top:var(--gap);padding:calc(var(--gap) * .62)
  calc(var(--gap) * 1.15);border:3px solid #19C3D6;border-radius:999px;
  font-family:ui-monospace,Consolas,monospace;font-size:var(--p);
  color:#19C3D6;font-weight:700;letter-spacing:.01em}
"""

MEDIDAS = {
    # No 9x16 a interface do Reels cobre a base da tela, entao o bloco senta
    # acima do centro em vez de no meio geometrico.
    "vertical": "--pad:76px;--faixa:12px;--h1:118px;--p:46px;--num:210px;"
                "--nota:32px;--selo:26px;--gap:34px;--col:928px;--just:center",
    "horizontal": "--pad:84px;--faixa:10px;--h1:112px;--p:44px;--num:196px;"
                  "--nota:30px;--selo:24px;--gap:28px;--col:1752px;--just:center",
}


def _sem_teto(svg: str) -> str:
    """Tira o `max-width` que o gerador de graficos poe no proprio SVG."""
    return re.sub(r'\s*style="max-width:\d+px"', "", svg, count=1)


def _graficos(d: dict, largura: int) -> list[tuple[str, str]]:
    """Dois graficos do relatorio, redesenhados no tamanho do video.

    Sao os MESMOS geradores de SVG do PDF — nao ha' uma segunda implementacao
    que possa divergir. O que muda e' a largura: 680px serve a uma pagina A4 e
    fica ilegivel num celular.
    """
    ea = {int(r["ano"]): r for r in d["emendas_ano"]}
    anos = sorted(ea)
    gen = {}
    for r in d["genero_cargo"]:
        gen.setdefault(int(r["cod_cargo"]), {})[r["genero"]] = int(r["n"])
    rot = {1: "Presidente", 3: "Governador", 5: "Senador",
           6: "Dep. Federal", 7: "Dep. Estadual"}
    fem = [(rot[c], 100 * gen[c].get("FEMININO", 0) / sum(gen[c].values()))
           for c in (7, 6, 5, 3, 1) if c in gen]

    svg_emendas = linhas(
        {"Empenhado": [float(ea[a]["empenhado"]) / 1e9 for a in anos],
         "Pago": [float(ea[a]["pago"]) / 1e9 for a in anos]},
        anos, {"Empenhado": ACENTO, "Pago": OK},
        largura=largura, altura=int(largura * 0.46), area=True,
        rotulo_y=lambda v: f"{v:.0f}")
    svg_genero = barras(
        fem, largura=largura, alt_barra=max(30, largura // 26),
        gap=max(10, largura // 80), cor=ACENTO,
        rotulo=lambda v: f"{v:.1f}%".replace(".", ","), max_valor=50)

    # O SVG nasce com `style="max-width:<largura>px"` para nao estourar numa
    # pagina A4. Estilo EMBUTIDO vence qualquer seletor da folha, entao a
    # regra `.grafico svg{max-width:none}` nao alcancava — o atributo sai
    # aqui, na origem.
    svg_emendas = _sem_teto(svg_emendas)
    svg_genero = _sem_teto(svg_genero)

    return [
        ("05-emendas",
         '<div class="titulo">Emendas parlamentares, em R$ bilhões</div>'
         f'<div class="grafico">{svg_emendas}</div>'
         '<div class="nota">O volume empenhado dobra entre 2022 e 2023. Não é '
         'efeito de mais parlamentares — são 559 em 2022 e 563 em 2023.</div>'),
        ("06-genero",
         '<div class="titulo">Mulheres entre as candidaturas, por cargo</div>'
         f'<div class="grafico">{svg_genero}</div>'
         '<div class="nota">A cota de 30% por gênero vale para as listas '
         'proporcionais e não alcança cargo majoritário. Onde não há cota, a '
         'proporção cai.</div>'),
    ]


def _quadros(d: dict) -> list[tuple[str, str]]:
    """(nome do arquivo, miolo HTML). Os numeros saem do dado, nunca digitados."""
    com_ficha = sum(int(r["n"]) for r in d["por_cargo"] if int(r["cod_cargo"]) <= 8)
    vagas = int(next(r for r in d["senado_vagas"] if int(r["ano"]) == 2026)["vagas"])
    sem_autor = int(d["fonte_emendas"][0]["sem_autor"])

    def n(v):
        return f"{v:,}".replace(",", ".")

    return [
        ("01-capa",
         "<h1>Dossiê<br>Eleitoral <em>2026</em></h1>"
         "<p>O que cada candidatura declarou ao TSE.</p>"),
        ("02-escala",
         f'<div class="numero">{n(com_ficha)}</div>'
         '<div class="rotulo">fichas, uma para cada candidatura a cargo '
         'disputado</div>'
         '<div class="nota">Perfil, patrimônio, trajetória, financiamento de '
         'campanha e atividade legislativa — com fonte e data em toda tela.</div>'),
        ("04-senado",
         f'<div class="numero">{vagas}</div>'
         '<div class="rotulo">cadeiras do Senado em disputa — dois terços '
         'da Casa</div>'
         '<div class="nota">Nesta eleição o voto para senador é duplo, e cada '
         'voto elege três pessoas: o titular e dois suplentes que não aparecem '
         'na urna.</div>'),
        ("07-lacuna",
         f'<div class="numero">{n(sem_autor)}</div>'
         '<div class="rotulo">emendas que o <b>Portal da Transparência</b> '
         'publica sem dizer quem foi o autor</div>'
         '<div class="nota">Não é omissão do TSE nem deste site: o arquivo em '
         'bloco da CGU traz "Sem informação" no campo de autoria. O site diz '
         'isso na tela — onde o dado não existe, a ausência fica escrita.</div>'),
        ("09-nao-faz",
         "<h1>Sem nota.<br>Sem ranking.<br><em>Sem cor de partido.</em></h1>"
         "<p>Registro público, não avaliação.</p>"),
        # O cartao anterior falava do PROJETO — "aberto, gratuito, codigo
        # publico". Isso interessa a quem ja' se convenceu. A chamada tem que
        # dizer o que a pessoa faz agora, e por que.
        ("10-cta",
         "<h1>Procure quem<br>você vai <em>votar</em>.</h1>"
         '<div class="cta">dossie-eleitoral.com</div>'
         f'<div class="nota">Gratuito e sem cadastro. {n(com_ficha)} fichas, '
         'com fonte e data em toda tela.</div>'),
    ]


# Paginas do site que entram como captura, com a altura POR FORMATO.
#
# A mesma pagina a 430px de largura e' muito mais alta que a 1440px — o texto
# quebra em mais linhas. Uma altura unica para os dois formatos fazia a rolagem
# do 16x9 terminar em varios segundos de fundo vazio.
#
# As alturas subestimam de proposito. Sobrar espaco e' defeito que aparece no
# video; faltar apenas mostra menos pagina, e a rolagem ja' nao chega ao rodape
# de qualquer jeito.
#
# Nenhuma ficha individual. O video mostra a BUSCA e a LISTAGEM — que provam que
# a coisa funciona sem promover ninguem.
# BUSCA = 'silva', e nao um nome proprio.
#
# "Xuxa do Amazonas" devolve TRES candidaturas: tres pessoas na tela, uma delas
# em evidencia. Num video de divulgacao isso e' destacar alguem, que e' o que
# este projeto nao faz.
#
# "silva" devolve 3.226. A tela enche de nomes, ninguem fica em evidencia, e o
# numero grande e' justamente o que prova que a busca funciona — mostrar a
# ferramenta achando muita coisa vende melhor que mostrar um caso curioso.
BUSCA = "maria"

# O que o HTML gerado usa como raiz. E' o que a captura troca pelo
# endereco do servidor local.
BASE_PROD = "https://datadubaintel.com/dossie-eleitoral"

# A altura em pixels de CSS decide o que acontece no video: quando ela cabe no
# quadro, a captura fica parada; quando passa, o video rola por ela.
#
# 03-busca fica PARADA — a informacao ali e' o campo preenchido e a lista de
# achados, e rolar por cima disso tira a atencao do que importa.
# (nome, caminho, altura visivel, ponto de partida) — tudo em pixels de CSS.
#
# O ponto de partida existe porque o topo de uma pagina e' cabecalho e titulo, e
# o que interessa no video esta' abaixo. Sem ele, o quadro da busca mostrava a
# barra de navegacao inteira e UMA linha de resultado.
CAPTURAS = {
    "vertical": [
        ("03-busca", f"index.html?q={BUSCA}", 764, 430),
        ("08-listagem", "senador/index.html", 2000, 260),
    ],
    "horizontal": [
        ("03-busca", f"index.html?q={BUSCA}", 810, 300),
        ("08-listagem", "senador/index.html", 1500, 200),
    ],
}

# Largura em pixels de CSS. 430 e' a de um celular grande: o site cai no layout
# mobile, que e' o que faz sentido dentro de um quadro 9x16. No 16x9 vale a
# largura de desktop, que e' o layout que o site foi desenhado para ter.
LARGURA_CSS = {"vertical": 430, "horizontal": 1440}


class _Servidor:
    """Serve `site/` por HTTP em 127.0.0.1, so' enquanto a captura roda.

    ── POR QUE NAO BASTA ABRIR O ARQUIVO ──

    A busca da home carrega o indice por `fetch`, e o endereco no HTML e'
    ABSOLUTO — aponta para datadubaintel.com. Aberta como `file://`, a pagina
    tenta buscar noutra origem e o navegador barra: o campo aparece preenchido e
    a lista vazia, com "nao foi possivel carregar a busca".

    Servindo por HTTP e reescrevendo a base para o proprio servidor, a busca
    passa a ser mesma-origem e funciona como funciona para quem visita o site.
    """

    def __init__(self, raiz):
        import functools
        import http.server
        import threading

        manipulador = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(raiz))
        # Porta 0: o sistema escolhe uma livre. Fixar porta e' como duas
        # execucoes simultaneas colidem.
        self._s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manipulador)
        self._s.RequestHandlerClass.log_message = lambda *_a, **_k: None
        self.base = f"http://127.0.0.1:{self._s.server_address[1]}"
        threading.Thread(target=self._s.serve_forever, daemon=True).start()

    def fechar(self):
        self._s.shutdown()
        self._s.server_close()


def _capturar_site(navegador: str, formato: str, larg: int, pasta) -> int:
    """Captura paginas do site, com a busca funcionando de verdade.

    O site fica em `site/`, gerado localmente. Se ainda nao existir, as capturas
    sao puladas e o video sai so' com os cartoes — melhor um video menor que um
    video com pagina em branco.
    """
    sitio = RAIZ / "site"
    if not (sitio / "index.html").exists():
        log.warning("site/ nao existe — capturas puladas (rode gerar_site antes)")
        return 0
    servidor = _Servidor(sitio)
    css = LARGURA_CSS[formato]
    escala = larg / css
    n = 0
    for nome, caminho, altura, topo in CAPTURAS[formato]:
        # `index.html?q=silva` — o parametro fica fora do teste de existencia.
        arquivo, _, query = caminho.partition("?")
        alvo = sitio / arquivo
        if not alvo.exists():
            log.warning("%s nao existe — captura pulada", caminho)
            continue
        # O `iframe` existe para fixar a largura de CSS: sem ele a janela do
        # navegador define a largura, e ai' nao da' para pedir layout de celular
        # e imagem de 1080px ao mesmo tempo.
        # Copia da pagina com a base trocada pelo servidor local. Sem isso o
        # `fetch` da busca continuaria indo para o dominio de producao.
        copia = sitio / f"_captura-{nome}.html"
        copia.write_text(
            alvo.read_text(encoding="utf-8").replace(BASE_PROD, servidor.base),
            encoding="utf-8")
        url = f"{servidor.base}/{copia.name}" + (f"?{query}" if query else "")

        moldura = TMP / f"{formato}-{nome}.html"
        moldura.write_text(
            f'<!doctype html><html><head><meta charset="utf-8"><style>'
            f'html,body{{margin:0;padding:0;background:#07172C}}'
            f'.janela{{width:{css}px;height:{altura}px;overflow:hidden}}'
            f'iframe{{width:{css}px;height:{altura + topo}px;border:0;'
            f'display:block;margin-top:-{topo}px}}'
            f'</style></head><body>'
            f'<div class="janela"><iframe src="{url}" scrolling="no"></iframe></div>'
            f'</body></html>', encoding="utf-8")
        try:
            _tirar(navegador, moldura.as_uri(), pasta / f"{nome}.png",
                   f"--force-device-scale-factor={escala:.4f}",
                   f"--window-size={css},{altura}",
                   # A busca carrega o indice por `fetch`; o tempo virtual da'
                   # ao navegador a chance de esperar a resposta antes da foto.
                   "--virtual-time-budget=8000")
        finally:
            copia.unlink(missing_ok=True)
        n += 1
    servidor.fechar()
    return n


def _tirar(navegador: str, alvo, png, *extras: str) -> None:
    """Uma execucao do navegador, com PERFIL PROPRIO e verificacao de escrita.

    ── POR QUE UM PERFIL POR CAPTURA ──

    Chrome e Edge tratam o diretorio de perfil como singleton: uma segunda
    instancia sobre o MESMO perfil delega para a primeira e sai com codigo ZERO
    sem fazer nada. Como o processo anterior nem sempre morre a tempo, as
    capturas seguintes saiam vazias — em silencio, com codigo de sucesso.

    Foi assim que uma execucao inteira "gerou 20 quadros" mantendo os arquivos
    da execucao anterior. `ignore_cleanup_errors` cobre o outro lado: o Edge
    ainda segura o `lockfile` quando o diretorio e' apagado.

    ── POR QUE APAGAR O DESTINO ANTES ──

    A verificacao de arquivo completo passava no arquivo VELHO quando o novo nao
    era escrito. Apagando antes, "existe e termina em IEND" volta a significar
    "foi escrito agora".
    """
    png.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as perfil:
        subprocess.run(
            [navegador, "--headless=new", "--disable-gpu",
             f"--user-data-dir={perfil}", "--no-first-run",
             "--no-default-browser-check", "--hide-scrollbars",
             *extras, f"--screenshot={png}", alvo],
            check=True, capture_output=True, timeout=240)
    for _ in range(40):
        if png.exists() and b"IEND" in png.read_bytes()[-12:]:
            return
        time.sleep(0.25)
    raise SystemExit(f"{png.name}: o navegador saiu sem escrever a imagem")


def _navegador() -> str:
    for c in (os.environ.get("EDGE"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              shutil.which("msedge"), shutil.which("chrome")):
        if c and Path(c).exists():
            return c
    raise SystemExit("nenhum navegador Chromium encontrado — defina EDGE=<caminho>")


def main() -> None:
    if not DADOS.exists():
        raise SystemExit(f"{DADOS} nao existe — rode antes: "
                         "python -m scripts.dados_relatorio")
    d = json.loads(DADOS.read_text(encoding="utf-8"))
    TMP.mkdir(parents=True, exist_ok=True)
    navegador = _navegador()
    n = 0
    for formato, (larg, alt) in FORMATOS.items():
        pasta = SAIDA / formato
        pasta.mkdir(parents=True, exist_ok=True)
        # O SVG e' gerado ESTREITO e esticado ate' a largura da coluna. Como
        # ele escala inteiro, um rotulo de 10px nasce com 22px na tela. Gerado
        # ja' na largura final, o mesmo rotulo ficaria com 10px — que e' o que
        # deixava o eixo X ilegivel.
        largura_svg = 430 if formato == "vertical" else 620
        for nome, miolo in _quadros(d) + _graficos(d, largura_svg):
            html = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                    f'<style>:root{{{MEDIDAS[formato]}}}{CSS}</style></head><body>'
                    f'<div class="faixa"></div><div class="miolo">{miolo}</div>'
                    f'<div class="selo">Data Duba Intelligence</div>'
                    f'<div class="url">dossie-eleitoral.com</div>'
                    f'</body></html>')
            origem = TMP / f"{formato}-{nome}.html"
            origem.write_text(html, encoding="utf-8")
            _tirar(navegador, origem.as_uri(), pasta / f"{nome}.png",
                   f"--window-size={larg},{alt}")
            n += 1
        n += _capturar_site(navegador, formato, larg, pasta)
    log.info("%d quadros em %s (%s)", n, SAIDA, " e ".join(FORMATOS))


if __name__ == "__main__":
    main()
