"""Normalizacao de texto e de valores das fontes brasileiras.

Tudo aqui e' puro e testavel sem rede — e' o nucleo que os testes do `tests/`
exercitam. Regras derivadas de SPEC §9 (snake_case pt-BR sem acento) e §5
(chave de pessoa, valores de bens).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import unicodedata
from datetime import date, datetime

from ingest.common.log import get_logger

log = get_logger("textnorm")

# Sentinelas de ausencia usadas pelo TSE. Viram NULL, nunca string literal.
NULL_TOKENS = frozenset(
    {"", "#NULO#", "#NULO", "#NE#", "#NE", "#N/A", "#NI#", "N/A", "NULO", "-1", "-3", "-4"}
)

# Salt publico de fallback: mantem `make run` reproduzivel do zero (Constituicao §4)
# mas NAO protege o CPF. Em producao defina RADAR_CPF_SALT. Ver docs/adr/ADR-006.
_DEFAULT_SALT = "radar-brasil-salt-publico-ver-ADR-006"
_salt_warned = False

_ACCENT_RE = re.compile(r"[\u0300-\u036f]")
_NON_WORD_RE = re.compile(r"[^0-9a-zA-Z]+")
_SPACES_RE = re.compile(r"\s+")
_DIGITS_RE = re.compile(r"\D+")


def strip_accents(value: str) -> str:
    """`Instrução` -> `Instrucao`."""
    return _ACCENT_RE.sub("", unicodedata.normalize("NFD", value))


def snake_case(value: str) -> str:
    """`DS_GRAU_INSTRUÇÃO` -> `ds_grau_instrucao` (SPEC §9)."""
    ascii_value = strip_accents(value).strip()
    # separa camelCase antes de achatar
    ascii_value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", ascii_value)
    return _NON_WORD_RE.sub("_", ascii_value).strip("_").lower()


def clean(value: str | None) -> str | None:
    """Trim + sentinelas do TSE viram None."""
    if value is None:
        return None
    stripped = _SPACES_RE.sub(" ", value.strip())
    if stripped.upper() in NULL_TOKENS:
        return None
    return stripped or None


def normalize_nome(value: str | None) -> str | None:
    """Nome para comparacao: sem acento, maiusculo, espaco unico.

    Usado no fallback de vinculacao de pessoa quando nao ha' CPF (SPEC §5).
    """
    cleaned = clean(value)
    if cleaned is None:
        return None
    return _SPACES_RE.sub(" ", strip_accents(cleaned).upper()).strip() or None


def only_digits(value: str | None) -> str | None:
    cleaned = clean(value)
    if cleaned is None:
        return None
    digits = _DIGITS_RE.sub("", cleaned)
    return digits or None


def cpf_salt() -> str:
    global _salt_warned
    salt = os.environ.get("RADAR_CPF_SALT")
    if not salt:
        if not _salt_warned:
            log.warning(
                "RADAR_CPF_SALT nao definido — usando salt publico de fallback. "
                "Os hashes sao reproduziveis, mas NAO protegem o CPF. Ver ADR-006."
            )
            _salt_warned = True
        return _DEFAULT_SALT
    return salt


def cpf_hash(cpf: str | None) -> str | None:
    """Chave de pessoa (SPEC §5 / ADR-005).

    HMAC-SHA256 e nao SHA-256 puro: o espaco de CPF tem 10^11 elementos e um
    hash sem chave e' enumeravel em minutos — o que devolveria o CPF que o
    projeto se comprometeu a nao expor (Constituicao §7). Ver ADR-006.
    """
    digits = only_digits(cpf)
    if digits is None or len(digits) != 11 or len(set(digits)) == 1:
        return None
    return hmac.new(cpf_salt().encode("utf-8"), digits.encode("ascii"), hashlib.sha256).hexdigest()


def pessoa_fallback_key(nome_completo: str | None, data_nascimento: str | None) -> str | None:
    """Chave alternativa quando o ano nao traz CPF: nome normalizado + nascimento.

    Quem usa esta chave e' marcado com `link_confiavel = false` no mart.
    """
    nome = normalize_nome(nome_completo)
    nasc = parse_data(data_nascimento)
    if not nome or not nasc:
        return None
    payload = f"{nome}|{nasc.isoformat()}"
    return hmac.new(cpf_salt().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%Y%m%d")


def parse_data(value: str | None) -> date | None:
    """`31/12/1970` -> date(1970,12,31). Datas-sentinela viram None."""
    cleaned = clean(value)
    if cleaned is None:
        return None
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
        # o TSE usa 1900 e 9999 como "sem informacao"
        if parsed.year <= 1900 or parsed.year >= 9999:
            return None
        return parsed
    return None


def parse_data_iso(value: str | None) -> str | None:
    parsed = parse_data(value)
    return parsed.isoformat() if parsed else None


def parse_decimal_br(value: str | None) -> float | None:
    """`1.234.567,89` -> 1234567.89 (valor de bem declarado, S2).

    Aceita tambem o formato ja' anglofono (`1234567.89`) porque alguns anos
    do TSE alternam. Distingue pelo separador que aparece por ultimo.
    """
    cleaned = clean(value)
    if cleaned is None:
        return None
    cleaned = cleaned.replace("R$", "").replace(" ", "").strip()
    if not cleaned:
        return None
    has_comma, has_dot = "," in cleaned, "." in cleaned
    if has_comma and has_dot:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_int(value: str | None) -> int | None:
    cleaned = clean(value)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned.replace(".", "").replace(",", ".")))
    except ValueError:
        return None


def parse_bool_sn(value: str | None) -> bool | None:
    """`S`/`N` do TSE -> booleano. Qualquer outra coisa vira None."""
    cleaned = clean(value)
    if cleaned is None:
        return None
    upper = strip_accents(cleaned).upper()
    if upper in {"S", "SIM", "TRUE", "1"}:
        return True
    if upper in {"N", "NAO", "FALSE", "0"}:
        return False
    return None
