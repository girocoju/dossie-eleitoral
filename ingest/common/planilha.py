"""Leitura de xlsx sem dependencia externa.

O `pyproject` declara que o nucleo da ingestao e' stdlib-only de proposito, e um
leitor de planilha nao justifica quebrar isso: xlsx e' um zip de XML.

Duas fontes do projeto entregam planilha, e as duas embrulham diferente:

    INEP/IDEB   zip que contem o xlsx
    Tesouro/RTN xlsx direto

`abrir` resolve os dois casos.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_DOC = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

_COL = re.compile(r"([A-Z]+)")


class Planilha:
    """Uma aba, indexada por REFERENCIA de celula.

    Indexar por posicao seria errado: o xlsx OMITE celulas vazias, entao a
    n-esima celula de uma linha nao e' a n-esima coluna. Uma unica celula em
    branco no meio deslocaria todas as colunas seguintes — e, num arquivo de
    serie historica, deslocaria todos os anos.
    """

    def __init__(self, z: zipfile.ZipFile, alvo: str, compart: list[str]) -> None:
        self._compart = compart
        raiz = ET.fromstring(z.read(alvo))
        self.linhas: dict[int, dict[str, str]] = {}
        for row in raiz.iter(f"{NS}row"):
            celulas: dict[str, str] = {}
            for c in row.iter(f"{NS}c"):
                m = _COL.match(c.get("r") or "")
                if m:
                    celulas[m.group(1)] = self._valor(c)
            self.linhas[int(row.get("r"))] = celulas

    def _valor(self, c: ET.Element) -> str:
        v = c.find(f"{NS}v")
        if v is None:
            return ""
        if c.get("t") == "s":
            return self._compart[int(v.text)]
        return v.text or ""

    def coluna(self, linha: int, col: str) -> str:
        return (self.linhas.get(linha) or {}).get(col, "")


def _abrir_zip(caminho: Path) -> zipfile.ZipFile:
    """Aceita o xlsx direto ou um zip que contenha um."""
    z = zipfile.ZipFile(caminho)
    if "xl/workbook.xml" in z.namelist():
        return z
    internos = [n for n in z.namelist() if n.endswith(".xlsx")]
    if not internos:
        raise ValueError(f"{caminho.name} nao e' xlsx nem contem um")
    return zipfile.ZipFile(io.BytesIO(z.read(internos[0])))


def abrir(caminho: Path, normalizar=None) -> dict[str, Planilha]:
    """Devolve {nome da aba: Planilha}.

    `normalizar` aplica-se ao NOME da aba, para o chamador poder casar sem
    depender de acento ou caixa.
    """
    z = _abrir_zip(caminho)

    compart: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        compart = [
            "".join(t.text or "" for t in si.iter(f"{NS}t"))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{NS}si")
        ]

    alvo_por_id = {
        r.get("Id"): "xl/" + (r.get("Target") or "").lstrip("/")
        for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(f"{NS_REL}Relationship")
    }

    abas: dict[str, Planilha] = {}
    for s in ET.fromstring(z.read("xl/workbook.xml")).iter(f"{NS}sheet"):
        alvo = alvo_por_id.get(s.get(f"{NS_DOC}id"))
        if alvo and alvo in z.namelist():
            nome = s.get("name") or ""
            abas[normalizar(nome) if normalizar else nome] = Planilha(z, alvo, compart)
    return abas
