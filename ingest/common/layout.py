"""Resolucao de layout do TSE contra o cabecalho real do CSV.

O contrato esta' em `ingest/layouts/README.md`. Aqui e' onde a regra
"nao adivinhar" (SPEC §9) vira codigo: nada e' mapeado por posicao nem por
heuristica de nome — so' pela lista de aliases declarada no YAML do ano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from ingest.common.log import get_logger
from ingest.common.textnorm import snake_case

log = get_logger("layout")

LAYOUT_DIR = Path(__file__).resolve().parents[1] / "layouts"


class LayoutError(RuntimeError):
    """Layout declarado nao bate com o arquivo real da fonte."""


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _norm_alias(nome: str) -> str:
    """Chave de comparacao de coluna: sem acento, sem aspas, sem espaco, minuscula."""
    return snake_case(nome.replace('"', "").replace("\ufeff", ""))


@dataclass(frozen=True)
class Resolucao:
    """Resultado de casar o layout declarado com o header real."""

    dataset: str
    ano: int
    header: tuple[str, ...]
    indices: dict[str, int]
    faltando_obrigatorios: tuple[str, ...]
    faltando_opcionais: tuple[str, ...]
    extras: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.faltando_obrigatorios


@dataclass(frozen=True)
class DatasetLayout:
    nome: str
    ano: int
    base_url: str
    pacote: str
    arquivo_regex: str
    leiame: str | None
    encoding: str
    delimitador: str
    campos: dict[str, list[str]]
    obrigatorios: tuple[str, ...]
    chave: tuple[str, ...]
    descartar: frozenset[str] = frozenset()
    hash_map: dict[str, str] = field(default_factory=dict)
    indisponivel: str | None = None
    # Agregacao na ingestao: `agregar_por` sao as colunas do grao de saida e
    # `somar` as que sao acumuladas. Existe para fontes grandes demais para irem
    # cruas ao warehouse — a votacao por municipio e zona tem ~10 milhoes de
    # linhas por eleicao, e o projeto so' precisa do total por candidatura.
    agregar_por: tuple[str, ...] = ()
    somar: tuple[str, ...] = ()
    ue_esperadas: int | None = None
    # Filtro declarativo aplicado na leitura: {campo: [valores aceitos]}. Existe
    # para fontes onde o recorte muda a ordem de grandeza — a votacao por
    # municipio tem ~70 milhoes de linhas somando as sete eleicoes, mas restrita a
    # presidente e governador cai para a casa do milhao.
    filtrar: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def agrega(self) -> bool:
        return bool(self.agregar_por and self.somar)

    def aceita(self, linha: dict[str, Any]) -> bool:
        """Aplica o filtro declarado. Sem filtro, tudo passa."""
        for campo, valores in self.filtrar.items():
            if str(linha.get(campo)) not in valores:
                return False
        return True

    def valida_agregacao(self) -> None:
        """A chave declarada tem de caber dentro do grao de agregacao.

        Se sobrar coluna na chave que nao esta' em `agregar_por`, a saida tem
        duplicatas POR CONSTRUCAO — e a trava de chave duplicada nao roda no
        caminho agregado, entao o erro passaria em silencio.
        """
        if not self.agrega:
            return
        faltando = [c for c in self.chave if c not in self.agregar_por]
        if faltando:
            raise LayoutError(
                f"{self.nome}: a chave {list(self.chave)} nao cabe no grao de "
                f"agregacao {list(self.agregar_por)} — faltam {faltando}. "
                f"Do jeito que esta', a saida teria duplicatas por construcao."
            )

    def colunas_saida(self) -> list[str]:
        """Colunas que de fato chegam ao BigQuery, na ordem do schema.

        Difere de `campos` em dois pontos: o que `privacidade.descartar` remove
        nunca aparece, e o que `privacidade.hash` cobre aparece com o nome do
        hash (`nr_cpf` -> `cpf_hash`). `ano_eleicao` sai daqui porque e' INT64
        e entra pelo argumento `inteiros` do schema — e' a coluna de particionamento.
        """
        saida: list[str] = []
        for canonico in self.campos:
            if canonico in self.descartar or canonico == "ano_eleicao":
                continue
            saida.append(self.hash_map.get(canonico, canonico))
        return saida

    @property
    def url(self) -> str:
        return f"{self.base_url}/{self.pacote.format(ano=self.ano)}"

    @property
    def zip_name(self) -> str:
        return self.pacote.format(ano=self.ano).rsplit("/", 1)[-1]

    @property
    def leiame_url(self) -> str | None:
        return f"{self.base_url}/{self.leiame}" if self.leiame else None

    def compila_regex(self) -> re.Pattern[str]:
        # `{ano}` e' o unico placeholder; `{2}` do regex nao pode ser tocado.
        return re.compile(self.arquivo_regex.replace("{ano}", str(self.ano)), re.IGNORECASE)

    def resolve(self, header: list[str]) -> Resolucao:
        """Casa cada campo canonico com uma coluna do header real."""
        por_alias: dict[str, int] = {}
        for idx, nome in enumerate(header):
            por_alias.setdefault(_norm_alias(nome), idx)

        indices: dict[str, int] = {}
        usados: set[int] = set()
        faltando: list[str] = []
        for canonico, aliases in self.campos.items():
            for alias in aliases:
                idx = por_alias.get(_norm_alias(alias))
                if idx is not None:
                    indices[canonico] = idx
                    usados.add(idx)
                    break
            else:
                faltando.append(canonico)

        obrig = tuple(c for c in faltando if c in self.obrigatorios)
        opc = tuple(c for c in faltando if c not in self.obrigatorios)
        extras = {
            _norm_alias(nome): idx
            for idx, nome in enumerate(header)
            if idx not in usados and _norm_alias(nome)
        }
        return Resolucao(
            dataset=self.nome,
            ano=self.ano,
            header=tuple(header),
            indices=indices,
            faltando_obrigatorios=obrig,
            faltando_opcionais=opc,
            extras=extras,
        )

    def exige(self, resolucao: Resolucao) -> None:
        """Falha alto quando um campo obrigatorio nao existe no arquivo real."""
        if resolucao.ok:
            return
        raise LayoutError(
            f"Layout de {self.nome} {self.ano} nao resolve os campos obrigatorios "
            f"{list(resolucao.faltando_obrigatorios)}.\n"
            f"Header real: {list(resolucao.header)}\n"
            f"Abra o leiame ({self.leiame_url or 'ver dadosabertos.tse.jus.br'}) e "
            f"atualize ingest/layouts/tse_{self.ano}.yml — nao altere o .py."
        )


@dataclass(frozen=True)
class Layout:
    ano: int
    verificado: bool
    notas: str
    _raw: dict[str, Any]

    @property
    def ue_esperadas(self) -> int | None:
        """Quantas unidades eleitorais o pacote do ano deve ter (27 UFs + BR)."""
        valor = self._raw.get("ue_esperadas")
        return int(valor) if valor else None

    @property
    def datasets(self) -> tuple[str, ...]:
        return tuple(self._raw.get("datasets", {}))

    def dataset(self, nome: str) -> DatasetLayout:
        try:
            spec = self._raw["datasets"][nome]
        except KeyError as exc:
            raise LayoutError(
                f"dataset '{nome}' nao existe no layout {self.ano}; "
                f"disponiveis: {list(self.datasets)}"
            ) from exc
        privacidade = self._raw.get("privacidade", {}) or {}
        return DatasetLayout(
            nome=nome,
            ano=self.ano,
            base_url=self._raw["base_url"].rstrip("/"),
            pacote=spec["pacote"],
            arquivo_regex=spec["arquivo_regex"],
            leiame=spec.get("leiame"),
            encoding=spec.get("encoding", self._raw.get("encoding", "latin-1")),
            delimitador=spec.get("delimitador", self._raw.get("delimitador", ";")),
            campos={k: list(v) for k, v in spec["campos"].items()},
            obrigatorios=tuple(spec.get("obrigatorios", ())),
            chave=tuple(spec.get("chave", ())),
            descartar=frozenset(privacidade.get("descartar", ()) or ()),
            hash_map=dict(privacidade.get("hash", {}) or {}),
            indisponivel=spec.get("indisponivel"),
            agregar_por=tuple(spec.get("agregar_por", ()) or ()),
            somar=tuple(spec.get("somar", ()) or ()),
            ue_esperadas=spec.get("ue_esperadas") or self.ue_esperadas,
            filtrar={
                campo: tuple(str(v) for v in valores)
                for campo, valores in (spec.get("filtrar") or {}).items()
            },
        )


@cache
def load_layout(ano: int, layout_dir: str | None = None) -> Layout:
    """Carrega `tse_{ano}.yml` resolvendo `extends` recursivamente."""
    base_dir = Path(layout_dir) if layout_dir else LAYOUT_DIR
    path = base_dir / f"tse_{ano}.yml"
    if not path.exists():
        disponiveis = sorted(p.stem.removeprefix("tse_") for p in base_dir.glob("tse_*.yml"))
        raise LayoutError(f"sem layout para {ano}. Existem: {disponiveis}")

    def _read(p: Path, vistos: set[Path]) -> dict[str, Any]:
        if p in vistos:
            raise LayoutError(f"ciclo de `extends` em {p.name}")
        vistos.add(p)
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        pai = data.pop("extends", None)
        if pai:
            return _deep_merge(_read(p.parent / pai, vistos), data)
        return data

    raw = _read(path, set())
    raw.setdefault("ano", ano)
    return Layout(
        ano=int(raw["ano"]),
        verificado=bool(raw.get("verificado", False)),
        notas=str(raw.get("notas", "")).strip(),
        _raw=raw,
    )


def anos_disponiveis(layout_dir: str | None = None) -> list[int]:
    base_dir = Path(layout_dir) if layout_dir else LAYOUT_DIR
    anos = []
    for p in base_dir.glob("tse_*.yml"):
        sufixo = p.stem.removeprefix("tse_")
        if sufixo.isdigit():
            anos.append(int(sufixo))
    return sorted(anos)
