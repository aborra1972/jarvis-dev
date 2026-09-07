"""Spanish orthography, punctuation and phonetic preparation for TTS."""

from __future__ import annotations

from jarvis.audio.pronunciation import normalize_for_tts


def test_normalize_adds_safe_orthographic_accents() -> None:
    assert (
        normalize_for_tts("PROXIMA PAGINA de configuracion")
        == "PRÓXIMA PÁGINA de configuración."
    )


def test_normalize_uses_curated_spanish_phonetics_for_foreign_terms() -> None:
    assert (
        normalize_for_tts("Google, GitHub, OpenCode y pytest")
        == "Gúgel, Guít Jab, Óupen Cóud y pái test."
    )


def test_normalize_keeps_natural_punctuation_and_decimal_numbers() -> None:
    assert normalize_for_tts("Hola , señor. Versión 3.14") == "Hola, señor. Versión 3.14."


def test_normalize_accepts_verified_custom_pronunciations() -> None:
    assert (
        normalize_for_tts("Linux listo", pronunciations={"Linux": "Línux"})
        == "Línux listo."
    )


def test_normalize_empty_text_stays_empty() -> None:
    assert normalize_for_tts("  ") == ""
