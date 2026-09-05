"""NLU fallback classifier (roadmap: "NLU classifier", study item #7).

TF-IDF + LogisticRegression trained on a small hand-curated seed corpus.
Used ONLY as a last-resort SUGGESTION when both the golden gate and the LLM
have already failed to resolve a transcript — this module never emits an
executable Intent. It only turns a bare "no entiendo, señor" into a
specific guess the interpreter can offer instead ("me pareció que quisiste
abrir una aplicación, ¿es así? repetí el comando, señor."), so the person
gets a useful hint instead of silence. The user still has to repeat/confirm
through the normal re-ask flow — this does not bypass golden or the LLM's
authority over what actually executes.

Deliberately excludes destructive intents (shutdown/reboot/power_off_self)
from its vocabulary entirely: per ADR-2, only the golden gate may ever
resolve those, and a probabilistic guess must never even hint at one.

The model trains lazily on first use (not at import time) since fitting
even a tiny TF-IDF+LogReg has a real cost we don't want to pay for every
`import jarvis.interpreter.interpreter` — only when golden and the LLM
have both already failed is this ever actually needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.interpreter.normalize import normalize
from jarvis.interpreter.schema import DESTRUCTIVE_INTENTS

# Seed corpus: a handful of natural-language examples per intent, covering
# the kind of phrasing real (noisy) STT output tends to produce. This is a
# small hand-curated MVP corpus, not a scraped/mined dataset — good enough
# to catch "close but not an exact golden-pattern match" transcripts, which
# is the actual failure mode this exists to soften. None of these intents
# are in DESTRUCTIVE_INTENTS (enforced by a startup assertion below).
_SEED_EXAMPLES: tuple[tuple[str, str], ...] = (
    # open_app
    ("abrir firefox", "open_app"),
    ("abri firefox", "open_app"),
    ("abrime el navegador", "open_app"),
    ("abrir la terminal", "open_app"),
    ("abrime spotify", "open_app"),
    ("abrir visual studio code", "open_app"),
    ("abrime el editor de codigo", "open_app"),
    ("abrir el explorador de archivos", "open_app"),
    ("abrime nautilus", "open_app"),
    ("abrir libreoffice", "open_app"),
    ("iniciar el navegador de internet", "open_app"),
    # web_search
    ("buscar recetas de pizza", "web_search"),
    ("busca el clima de hoy", "web_search"),
    ("buscame informacion sobre python", "web_search"),
    ("googlea el resultado del partido", "web_search"),
    ("buscar en internet noticias de hoy", "web_search"),
    ("busca cuanto sale el dolar", "web_search"),
    ("fijate en internet como se hace un asado", "web_search"),
    # ask
    ("preguntale a opencode que hace este archivo", "ask"),
    ("pregunta si el codigo tiene errores", "ask"),
    ("consultale al agente sobre el bug", "ask"),
    ("preguntale que significa este error", "ask"),
    ("preguntale al asistente de codigo por la funcion", "ask"),
    # execute
    ("corre git status", "execute"),
    ("ejecuta ls menos la", "execute"),
    ("corre el comando pwd", "execute"),
    ("ejecutar npm install", "execute"),
    ("corre python main punto pi", "execute"),
    ("ejecutame el script de build", "execute"),
    # help
    ("que podes hacer", "help"),
    ("ayuda", "help"),
    ("que comandos tenes", "help"),
    ("como te uso", "help"),
    ("que funciones tenes disponibles", "help"),
    # general_qa
    ("que hora es", "general_qa"),
    ("que dia es hoy", "general_qa"),
    ("cual es la capital de francia", "general_qa"),
    ("cuanto es dos mas dos", "general_qa"),
    ("contame un dato curioso", "general_qa"),
    # open_repo
    ("abrir el proyecto jarvis", "open_repo"),
    ("abri el repositorio de trabajo", "open_repo"),
    ("abrime el proyecto de la app", "open_repo"),
    ("abrir el repo que estaba usando", "open_repo"),
)

assert not {label for _, label in _SEED_EXAMPLES} & DESTRUCTIVE_INTENTS, (
    "NLU classifier must never be trained on a destructive intent (ADR-2)"
)

MIN_CONFIDENCE = 0.25  # empirically measured tradeoff (see tests): with this
# tiny a seed corpus and 7 classes, there's no threshold that's both
# reliably right AND reliably quiet — 0.20 catches more real commands but
# also fires on casual talk ("hola como estás"); 0.30+ stays quiet on talk
# but misses real commands too often. 0.25 is a middle ground: it's a
# SUGGESTION the user still has to confirm/repeat, so occasional wrong
# guesses are a minor annoyance, not a safety issue — but staying silent
# too often defeats the point of having this at all.

_SPOKEN_BY_INTENT: dict[str, str] = {
    "open_app": "abrir una aplicación",
    "web_search": "buscar algo en internet",
    "ask": "consultarle algo a OpenCode",
    "execute": "ejecutar un comando",
    "help": "pedir ayuda",
    "general_qa": "hacer una pregunta general",
    "open_repo": "abrir un proyecto",
}


@dataclass(frozen=True)
class Suggestion:
    """A non-executable guess — the caller may only speak `spoken`."""

    intent: str
    confidence: float
    spoken: str


class _LazyModel:
    """Fits the TF-IDF + LogisticRegression pipeline once, on first use."""

    _vectorizer = None
    _model = None

    @classmethod
    def get(cls):
        if cls._model is None:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression

            texts = [normalize(text, canonicalize=True) for text, _ in _SEED_EXAMPLES]
            labels = [label for _, label in _SEED_EXAMPLES]
            vectorizer = TfidfVectorizer(analyzer="word", ngram_range=(1, 2))
            matrix = vectorizer.fit_transform(texts)
            model = LogisticRegression(max_iter=1000)
            model.fit(matrix, labels)
            cls._vectorizer = vectorizer
            cls._model = model
        return cls._vectorizer, cls._model

    @classmethod
    def _reset_for_tests(cls) -> None:
        cls._vectorizer = None
        cls._model = None


def classify(text: str, *, min_confidence: float = MIN_CONFIDENCE) -> Suggestion | None:
    """Best-effort intent guess for a transcript neither golden nor the LLM
    could resolve. Returns None (never raises) if: text is empty,
    scikit-learn isn't installed, or no class clears `min_confidence`.

    The returned Suggestion is for SPEAKING ONLY — the caller must never
    treat it as an executable Intent or skip re-asking the user.
    """
    if not text or not text.strip():
        return None
    canonical = normalize(text, canonicalize=True)
    if not canonical:
        return None
    try:
        vectorizer, model = _LazyModel.get()
        vector = vectorizer.transform([canonical])
        proba = model.predict_proba(vector)[0]
        best_idx = proba.argmax()
        confidence = float(proba[best_idx])
        intent = str(model.classes_[best_idx])
    except Exception:
        return None
    if confidence < min_confidence:
        return None
    spoken = _SPOKEN_BY_INTENT.get(intent)
    if spoken is None:  # pragma: no cover — defensive, every trained label is mapped
        return None
    return Suggestion(intent=intent, confidence=confidence, spoken=spoken)
