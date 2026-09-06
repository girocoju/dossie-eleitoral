"""Cartao de compartilhamento (Open Graph), 1200x630.

    python -m scripts.gerar_cartao

E' a imagem que o WhatsApp, o LinkedIn e o X mostram quando alguem cola o link.
Sem ela, o link vai sem imagem nenhuma — que era o caso ate' 05/09/2026.

── POR QUE NAO O LOGO OFICIAL DAS ELEICOES ──

O logo "Eleicoes 2026" e' do TSE. Usa-lo aqui faria todo link compartilhado
parecer vir da Justica Eleitoral. Este projeto organiza dado publico e NAO e' a
fonte: e' a mesma razao pela qual cor de partido nunca e' padrao visual (SPEC 0)
— nao emprestar autoridade nem filiacao que nao se tem. Alem de ser marca de
terceiro num material de portfolio comercial.

── POR QUE NAO HA' NUMERO NA IMAGEM ──

"20.858 candidaturas" seria uma boa linha. Mas o WhatsApp e o LinkedIn guardam o
cartao em cache por semanas, e a imagem em cache e' o unico lugar do projeto onde
um numero errado NAO pode ser corrigido republicando. Um projeto que apaga o
numero da tela quando a fonte nao sustenta nao pode deixar um numero congelado
onde ele nao alcanca.

── POR QUE UM CARTAO SO', E NAO UM POR FICHA ──

Um cartao por candidato seria mais informativo e traria dois problemas. A foto de
urna e' 3x4 e o formato do cartao e' 1,91x1 — o corte deforma o rosto. E o rosto
de uma pessoa como cartao de um link se le' como divulgacao dela, que e'
exatamente o que a Constituicao do projeto evita. O cartao neutro diz o que o
site e', e a ficha diz o resto.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ingest.common.log import get_logger

log = get_logger("cartao")

RAIZ = Path(__file__).resolve().parents[1]
HTML = RAIZ / "data" / "relatorio" / "cartao.html"
PNG = RAIZ / "og-dossie-eleitoral.png"
LARGURA, ALTURA = 1200, 630

# As cores sao as do tema ESCURO da folha do site — o cartao aparece sobre a
# conversa do WhatsApp, que e' escura na maioria dos aparelhos, e um retangulo
# branco ali grita.
PAGINA = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<style>
  @font-face{{font-family:x}}
  *{{box-sizing:border-box;margin:0}}
  html,body{{width:{LARGURA}px;height:{ALTURA}px}}
  body{{background:#07172C;color:#EAF1FA;
    font-family:Calibri,Carlito,"Segoe UI",Arial,sans-serif;
    display:flex;flex-direction:column;justify-content:space-between;
    padding:64px 72px;position:relative;overflow:hidden}}
  /* Faixa de destaque no topo: a mesma cor de acento do site. */
  .faixa{{position:absolute;top:0;left:0;right:0;height:10px;background:#19C3D6}}
  .marca{{font-family:ui-monospace,Consolas,monospace;font-size:19px;
    letter-spacing:.22em;text-transform:uppercase;color:#9FB2CD}}
  h1{{font-size:88px;line-height:1.02;letter-spacing:-.015em;font-weight:700}}
  h1 span{{color:#19C3D6}}
  p{{font-size:31px;line-height:1.36;color:#AEBFD6;max-width:20ch}}
  .pe{{display:flex;align-items:flex-end;justify-content:space-between;gap:24px}}
  .url{{font-family:ui-monospace,Consolas,monospace;font-size:25px;color:#19C3D6}}
  .nota{{font-size:19px;color:#7E90AB;text-align:right;line-height:1.4}}
</style></head><body>
  <div class="faixa"></div>
  <div class="marca">Data Duba Intelligence</div>
  <div>
    <h1>Dossiê<br>Eleitoral <span>2026</span></h1>
    <p style="margin-top:22px">O que cada candidatura declarou ao TSE.</p>
  </div>
  <div class="pe">
    <div class="url">dossie-eleitoral.com</div>
    <div class="nota">Apartidário · sem ranking<br>fonte e data em toda tela</div>
  </div>
</body></html>"""


def _navegador() -> str:
    """O Edge, que ja' vem no Windows. Mesmo caminho do relatorio em PDF."""
    for c in (os.environ.get("EDGE"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              shutil.which("msedge"), shutil.which("chrome"),
              shutil.which("chromium")):
        if c and Path(c).exists():
            return c
    raise SystemExit("nenhum navegador Chromium encontrado — defina EDGE=<caminho>")


def main() -> None:
    HTML.parent.mkdir(parents=True, exist_ok=True)
    HTML.write_text(PAGINA, encoding="utf-8")
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run(
            [_navegador(), "--headless=new", "--disable-gpu",
             f"--user-data-dir={perfil}",
             f"--window-size={LARGURA},{ALTURA}",
             "--default-background-color=00000000",
             "--hide-scrollbars",
             f"--screenshot={PNG}", HTML.as_uri()],
            check=True, capture_output=True, timeout=180)
    # O navegador sai antes de terminar de gravar; `IEND` e' o fim de um PNG.
    for _ in range(40):
        if PNG.exists() and PNG.read_bytes()[-12:].find(b"IEND") >= 0:
            break
        time.sleep(0.25)
    else:
        raise SystemExit("o PNG ficou incompleto (sem IEND)")
    log.info("%s — %d KB", PNG.name, round(PNG.stat().st_size / 1024))


if __name__ == "__main__":
    main()
