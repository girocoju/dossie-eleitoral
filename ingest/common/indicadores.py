"""Catalogo de indicadores e o formato longo comum a todas as fontes.

Todo indicador — venha do SIDRA, do Ipeadata ou de um arquivo — chega ao BigQuery
com o MESMO grao: `(cod_indicador, sg_uf, ano) -> valor` (SPEC 5,
`fct_indicador_uf_ano`). Isso e' o que permite comparar PIB e homicidios no mesmo
eixo de tempo sem uma tabela por fonte.

`sg_uf = 'BR'` guarda o agregado nacional, que e' o comparador obrigatorio da
Constituicao 0.2: nenhum numero de UF aparece na tela sem o do Brasil ao lado.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ingest.common.log import get_logger

log = get_logger("indicadores")

CATALOGO_PATH = Path(__file__).resolve().parents[1] / "layouts" / "indicadores.yml"

DIRECOES = frozenset({"cima", "baixo", "neutro"})
PROVEDORES = frozenset({"sidra", "ipeadata", "arquivo", "derivado"})


class CatalogoError(RuntimeError):
    """Catalogo de indicadores mal formado."""


@dataclass(frozen=True)
class Indicador:
    cod_indicador: str
    nome: str
    fonte: str
    unidade: str
    periodicidade: str
    direcao_desejavel: str
    provedor: str
    verificado: bool
    notas: str = ""
    conferido_em: str | None = None
    parametros: dict[str, Any] = field(default_factory=dict)

    @property
    def ingerivel(self) -> bool:
        """`derivado` nasce no dbt; `arquivo` sem URL ainda nao tem de onde vir."""
        if self.provedor == "derivado":
            return False
        if self.provedor == "arquivo":
            return bool(self.parametros.get("url"))
        return True


@dataclass(frozen=True)
class Observacao:
    """Uma linha do formato longo."""

    cod_indicador: str
    sg_uf: str
    ano: int
    valor: float | None
    unidade: str
    fonte: str
    n_periodos: int = 1
    extracted_at: str = ""
    source_url: str = ""

    def to_row(self) -> dict[str, Any]:
        linha = asdict(self)
        linha["_extracted_at"] = linha.pop("extracted_at")
        linha["_source_url"] = linha.pop("source_url")
        return linha


COLUNAS_SAIDA: tuple[str, ...] = (
    "cod_indicador",
    "sg_uf",
    "unidade",
    "fonte",
)
COLUNAS_NUMERICAS: tuple[tuple[str, str], ...] = (
    ("ano", "INT64"),
    ("n_periodos", "INT64"),
    ("valor", "FLOAT64"),
)


@lru_cache(maxsize=1)
def carregar_catalogo(path: str | None = None) -> dict[str, Indicador]:
    origem = Path(path) if path else CATALOGO_PATH
    bruto = yaml.safe_load(origem.read_text(encoding="utf-8")) or {}
    itens = bruto.get("indicadores") or {}
    if not itens:
        raise CatalogoError(f"{origem} nao declara nenhum indicador")

    catalogo: dict[str, Indicador] = {}
    for cod, spec in itens.items():
        faltando = [c for c in ("nome", "fonte", "unidade", "provedor") if c not in spec]
        if faltando:
            raise CatalogoError(f"indicador {cod}: faltam os campos {faltando}")
        if spec["provedor"] not in PROVEDORES:
            raise CatalogoError(
                f"indicador {cod}: provedor '{spec['provedor']}' desconhecido "
                f"(use um de {sorted(PROVEDORES)})"
            )
        direcao = spec.get("direcao_desejavel", "neutro")
        if direcao not in DIRECOES:
            raise CatalogoError(
                f"indicador {cod}: direcao_desejavel '{direcao}' invalida "
                f"(use um de {sorted(DIRECOES)})"
            )
        catalogo[cod] = Indicador(
            cod_indicador=cod,
            nome=spec["nome"],
            fonte=spec["fonte"],
            unidade=spec["unidade"],
            periodicidade=spec.get("periodicidade", "anual"),
            direcao_desejavel=direcao,
            provedor=spec["provedor"],
            verificado=bool(spec.get("verificado", False)),
            notas=str(spec.get("notas", "")).strip(),
            conferido_em=spec.get("conferido_em"),
            parametros=dict(spec.get("parametros") or {}),
        )
    return catalogo


def por_provedor(provedor: str, path: str | None = None) -> list[Indicador]:
    return [i for i in carregar_catalogo(path).values() if i.provedor == provedor]


def media_anual(
    valores_por_periodo: Iterable[tuple[int, float]], *, min_periodos: int = 1
) -> dict[int, tuple[float, int]]:
    """Trimestral -> anual. Ano com menos de `min_periodos` medidas e' descartado.

    Descartar em vez de extrapolar e' deliberado: um ano com 2 trimestres viraria
    um ponto que parece comparavel aos outros e nao e'. O que falta vai para
    docs/LACUNAS.md (SPEC 9), nunca para a serie.
    """
    acumulado: dict[int, list[float]] = {}
    for ano, valor in valores_por_periodo:
        acumulado.setdefault(ano, []).append(valor)
    resultado: dict[int, tuple[float, int]] = {}
    for ano, valores in acumulado.items():
        if len(valores) < min_periodos:
            log.info(
                "ano %s descartado: %d periodo(s), minimo %d", ano, len(valores), min_periodos
            )
            continue
        resultado[ano] = (sum(valores) / len(valores), len(valores))
    return resultado
