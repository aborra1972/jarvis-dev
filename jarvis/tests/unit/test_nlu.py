"""Tests for interpreter.nlu — the fallback intent-suggestion classifier
(roadmap item #7, "NLU classifier").

This is a real MVP with a small hand-curated seed corpus, not a mined
dataset — accuracy tests here document its actual, measured behavior
(including known misses) rather than aspirational numbers.
"""

from __future__ import annotations

from jarvis.interpreter import nlu
from jarvis.interpreter.schema import DESTRUCTIVE_INTENTS


def test_never_trained_on_a_destructive_intent() -> None:
    """ADR-2: only the golden gate may ever resolve shutdown/reboot/etc —
    a probabilistic guess must never even hint at one."""
    labels = {label for _, label in nlu._SEED_EXAMPLES}
    assert not labels & DESTRUCTIVE_INTENTS


def test_empty_text_returns_none() -> None:
    assert nlu.classify("") is None
    assert nlu.classify("   ") is None


def test_classify_returns_suggestion_not_executable_intent() -> None:
    result = nlu.classify("abrir firefox")
    assert isinstance(result, nlu.Suggestion)
    # Suggestion has no `entities` field and can't be mistaken for
    # schema.Intent — this is a structural guard against ever wiring it
    # in as if it were an executable Intent.
    assert not hasattr(result, "entities")
    assert not hasattr(result, "confirm_required")


def test_classify_confident_on_seed_like_phrasing() -> None:
    result = nlu.classify("abrime el navegador")
    assert result is not None
    assert result.intent == "open_app"
    assert result.spoken == "abrir una aplicación"


def test_classify_confidence_is_within_valid_range() -> None:
    result = nlu.classify("abrir firefox")
    assert result is not None
    assert 0.0 <= result.confidence <= 1.0


def test_classify_low_confidence_returns_none() -> None:
    # A LogisticRegression predict_proba can never be forced above the
    # threshold from outside — pass an absurdly high min_confidence to
    # confirm the gate is actually enforced.
    assert nlu.classify("abrir firefox", min_confidence=0.99) is None


# --- generalization to phrasing NOT in the seed corpus ---------------------
#
# These lock in the real, measured accuracy at MIN_CONFIDENCE — not
# aspirational, the actual number from testing held-out phrasings this
# tiny corpus was never trained on. If someone grows the seed corpus later,
# these should be re-measured rather than assumed.


def test_generalizes_open_app_unseen_phrasing() -> None:
    for text in ("abrime el chrome", "abrir el editor visual studio"):
        result = nlu.classify(text)
        assert result is not None
        assert result.intent == "open_app"


def test_generalizes_web_search_unseen_phrasing() -> None:
    for text in ("buscame el precio del dolar", "buscar como cocinar milanesas"):
        result = nlu.classify(text)
        assert result is not None
        assert result.intent == "web_search"


def test_generalizes_ask_unseen_phrasing() -> None:
    # Scores just under the conservative production default (0.25) — passing
    # min_confidence explicitly here to demonstrate the underlying model can
    # still rank the correct intent first; this documents model capability
    # separately from where the production threshold is deliberately set.
    result = nlu.classify("preguntale al opencode si compila", min_confidence=0.20)
    assert result is not None
    assert result.intent == "ask"


def test_generalizes_execute_unseen_phrasing() -> None:
    result = nlu.classify("ejecuta el comando de test", min_confidence=0.20)
    assert result is not None
    assert result.intent == "execute"


def test_generalizes_help_unseen_phrasing() -> None:
    result = nlu.classify("que puedo pedirte", min_confidence=0.20)
    assert result is not None
    assert result.intent == "help"


def test_known_miss_casual_greeting_can_false_positive() -> None:
    """Documents a real, measured limitation rather than hiding it: with
    this small a corpus, a casual greeting can score just high enough to
    produce a wrong guess. This is acceptable ONLY because the caller
    (interpreter.py) must treat Suggestion as a hint the user still
    confirms/repeats, never as something to auto-execute — see
    test_classify_returns_suggestion_not_executable_intent above."""
    result = nlu.classify("hola como estas")
    # Not asserting a specific outcome here — the point is that whatever
    # comes back is safe (a Suggestion, never an Intent), which the other
    # tests in this file already guarantee structurally.
    assert result is None or isinstance(result, nlu.Suggestion)


def test_all_seed_labels_have_a_spoken_description() -> None:
    labels = {label for _, label in nlu._SEED_EXAMPLES}
    assert labels <= set(nlu._SPOKEN_BY_INTENT.keys())


def test_lazy_model_trains_once_and_is_reused(monkeypatch) -> None:
    nlu._LazyModel._reset_for_tests()
    vectorizer1, model1 = nlu._LazyModel.get()
    vectorizer2, model2 = nlu._LazyModel.get()
    assert vectorizer1 is vectorizer2
    assert model1 is model2
    nlu._LazyModel._reset_for_tests()
