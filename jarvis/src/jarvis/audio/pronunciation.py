"""Deterministic Spanish text preparation before speech synthesis."""

from __future__ import annotations

import re
from collections.abc import Mapping

DEFAULT_PRONUNCIATIONS: dict[str, str] = {
    "Google": "Gúgel",
    "GitHub": "Guít Jab",
    "OpenCode": "Óupen Cóud",
    "pytest": "pái test",
}

_ORTHOGRAPHY: dict[str, str] = {
    "accion": "acción",
    "aplicacion": "aplicación",
    "codigo": "código",
    "configuracion": "configuración",
    "conversacion": "conversación",
    "despues": "después",
    "diagnostico": "diagnóstico",
    "ejecucion": "ejecución",
    "maquina": "máquina",
    "modulo": "módulo",
    "navegacion": "navegación",
    "numero": "número",
    "operacion": "operación",
    "pagina": "página",
    "proxima": "próxima",
    "proximo": "próximo",
    "sesion": "sesión",
    "tambien": "también",
}


def _match_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _replace_words(text: str, replacements: Mapping[str, str]) -> str:
    for source, replacement in replacements.items():
        pattern = rf"(?<!\w){re.escape(source)}(?!\w)"
        text = re.sub(
            pattern,
            lambda match: _match_case(match.group(0), replacement),
            text,
            flags=re.IGNORECASE,
        )
    return text


def normalize_for_tts(
    text: str,
    *,
    pronunciations: Mapping[str, str] | None = None,
) -> str:
    """Apply curated accents, phonetics and punctuation without custom SSML."""
    prepared = " ".join(text.strip().split())
    if not prepared:
        return ""
    prepared = _replace_words(prepared, _ORTHOGRAPHY)
    prepared = _replace_words(
        prepared,
        DEFAULT_PRONUNCIATIONS if pronunciations is None else pronunciations,
    )
    prepared = re.sub(r"\s+([,.;:!?])", r"\1", prepared)
    if prepared[-1] not in ".!?":
        prepared += "."
    return prepared
