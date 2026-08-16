"""Rioplatense text normalization for the command interpreter (PR2, task 2.2).

Pure, deterministic pipeline (design "Interpreter (hybrid, safe)"):
    lowercase → strip accents → strip punctuation → strip leading wake-word
    token(s) → canonicalize rioplatense verb forms (voseo/imperative →
    infinitive) → collapse whitespace

The canonical forms are what the golden gate and the LLM prompt consume, so a
single normalized surface keeps the regex surface minimal.
"""

from __future__ import annotations

import re
import unicodedata

# Leading wake-word token(s): optional greeting prefix + "jarvis" (RF-1).
# Includes common Whisper mishearings: charvis, shavis, sharvis, jarves, etc.
_WAKE_STRIP = re.compile(
    r"^\s*(?:(?:hey|hola|ok|oye|ejem|atencion|disculpa)\s+)?"
    r"(?:jarvis|charvis|shavis|sharvis|jarves|jarviss|chavis|sharrouiss|jorvis|yorvis)\s*"
)
_WS = re.compile(r"\s+")

# Rioplatense variants → canonical infinitive (table-driven).
# Phrase-level entries come first (modal + verb), then single words.
VARIANT_MAP: dict[str, str] = {
    # --- phrase-level: modal + verb ---
    "podes abrir": "abrir",
    "podes abrirme": "abrir",
    "podes buscar": "buscar",
    "podes buscarme": "buscar",
    "podes preguntar": "preguntar",
    "podes preguntarle": "preguntar",
    "podes cerrar": "cerrar",
    "podes apagar": "apagar",
    "podrias abrir": "abrir",
    "podrias buscar": "buscar",
    "podrias preguntarle": "preguntar",
    "podrias cerrar": "cerrar",
    "podrias apagar": "apagar",
    # --- word-level: voseo/imperative → infinitive ---
    "abri": "abrir",
    "abril": "abrir",  # Whisper commonly mishears "abrí" as "abril"
    "abrime": "abrir",
    "abrite": "abrir",
    "abrelo": "abrir",
    "abre": "abrir",
    "busca": "buscar",
    "buscame": "buscar",
    "buscale": "buscar",
    "buscala": "buscar",
    "buscarlo": "buscar",
    "pregunta": "preguntar",
    "preguntale": "preguntar",
    "preguntame": "preguntar",
    "preguntarle": "preguntar",
    "pedile": "pedir",
    "pedi": "pedir",
    "ayudame": "ayudar",
    "ayuda": "ayudar",
    "arma": "armar",
    "armame": "armar",
    "crea": "crear",
    "creame": "crear",
    "crealo": "crear",
    "setea": "setear",
    "setealo": "setear",
    "seteala": "setear",
    "configura": "configurar",
    "configurame": "configurar",
    "implementa": "implementar",
    "implementame": "implementar",
    "implementalo": "implementar",
    "revisa": "revisar",
    "revisame": "revisar",
    "cerra": "cerrar",
    "cerrame": "cerrar",
    "cerrate": "cerrar",
    "cerralo": "cerrar",
    "apaga": "apagar",
    "apagalo": "apagar",
    "apagate": "apagarse",
    "apagame": "apagarse",
    "reinicia": "reiniciar",
    "reiniciame": "reiniciar",
    "dormite": "dormirse",
    "borra": "borrar",
    "borrame": "borrar",
    "mostrame": "mostrar",
    "mostra": "mostrar",
    "muestrame": "mostrar",
    "muestra": "mostrar",
    "encende": "encender",
    "enciende": "encender",
    "saca": "sacar",
    "sacame": "sacar",
    "baja": "bajar",
    "bajame": "bajar",
    "instala": "instalar",
    "instalame": "instalar",
    "anota": "anotar",
    "anotame": "anotar",
}

# Word-boundary replacements (longest keys first preserves phrase entries).
_CANONICAL: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"\b{re.escape(src)}\b"), dst) for src, dst in VARIANT_MAP.items()
]


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str, canonicalize: bool = True) -> str:
    """Normalize a raw transcript to the command surface.

    With ``canonicalize=True`` (default) rioplatense variants are mapped to
    canonical infinitives — the surface the golden gate matches. With
    ``canonicalize=False`` the verb table is skipped so free-text entities
    (ask/web_search queries) keep the user's original wording instead of
    being corrupted ("se crea" must not become "se crear").
    """
    lowered = text.lower()
    no_accents = _strip_accents(lowered)
    # Keep letters, digits and safe separators (- _ .); everything else is
    # replaced by a space. Stripping shell metachars here neutralizes them for
    # the golden path (entity validation still guards the LLM path).
    no_punct = re.sub(r"[^a-z0-9\s._-]", " ", no_accents)
    without_wake = _WAKE_STRIP.sub("", no_punct, count=1)
    result = without_wake
    if canonicalize:
        for pattern, replacement in _CANONICAL:
            result = pattern.sub(replacement, result)
    return _WS.sub(" ", result).strip()
