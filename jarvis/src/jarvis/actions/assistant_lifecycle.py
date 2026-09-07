"""Assistant lifecycle executor (PR4, task 4.7).

Design (binding: single location): power_off_self lives ONLY here and is
golden-gated + 15s-confirmed by the orchestrator; the executor only logs and
acknowledges. handle_help enumerates the 18-command allowlist. handle_general_qa
provides direct LLM responses for general knowledge questions. handle_register_voice
enrolls the user's voice for speaker verification.
"""

from __future__ import annotations

import logging
import re

from jarvis.actions import base
from jarvis import config
from jarvis.interpreter.schema import ALLOWED_INTENTS, Intent
from jarvis.orchestrator.contracts import ActionResult

logger = logging.getLogger("jarvis.actions")


def power_off_self(intent: Intent, session: object) -> ActionResult:
    base.log("power_off_self")
    return ActionResult(ok=True, spoken=f"Muy bien, {config.agent_address()}. Me apago.")


def handle_help(intent: Intent, session: object) -> ActionResult:
    commands = ", ".join(sorted(ALLOWED_INTENTS - {"unknown"}))
    return ActionResult(
        ok=True, spoken=f"A su disposición, {config.agent_address()}. Puedo: {commands}"
    )


def handle_register_voice(intent: Intent, session: object) -> ActionResult:
    """Enroll the current speaker's voice for verification.

    Records audio from the microphone, extracts speaker embedding, and saves it.
    """
    try:
        from jarvis.speaker import get_verifier

        verifier = get_verifier()

        if verifier.is_enrolled():
            return ActionResult(
                ok=True,
                spoken=f"Ya tengo registrado mi voz, {config.agent_address()}. Si quiere actualizarla, "
                       "primero debe borrar el archivo speaker_embedding.json y "
                       "volver a registrar."
            )

        # Record and enroll
        logger.info("Starting voice enrollment...")
        success = verifier.enroll_from_mic(duration=10)

        if success:
            logger.info("Voice enrollment successful")
            return ActionResult(
                ok=True,
                spoken=f"Perfecto, {config.agent_address()}. Ya tengo registrada mi voz. "
                       "Ahora solo responderé a usted."
            )
        else:
            return ActionResult(
                ok=True,
                spoken=f"No pude registrar mi voz, {config.agent_address()}. "
                       "Asegúrese de que el micrófono funciona y "
                       "hable durante al menos 5 segundos."
            )

    except Exception as exc:
        logger.error("Voice enrollment failed: %s", exc)
        return ActionResult(
            ok=True,
            spoken=f"Error al registrar mi voz, {config.agent_address()}. Intente de nuevo."
        )


def handle_general_qa(intent: Intent, session: object) -> ActionResult:
    """Answer a general knowledge question using the LLM directly.

    Routes through Ollama/Gemini depending on config, returns the response
    as spoken text for TTS synthesis.
    """
    query = intent.entities.get("query", "")
    if not query:
        return ActionResult(ok=False, spoken=f"No recibí la pregunta, {config.agent_address()}.")

    try:
        # Build provider from config (same as interpreter)
        from jarvis.interpreter.llm import OllamaProvider, GeminiProvider, FallbackProvider
        import json
        import urllib.request
        import urllib.error

        provider_mode = config.LLM_PROVIDER
        ollama = OllamaProvider(
            model=config.INTERPRETER_LLM_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            timeout=config.OLLAMA_TIMEOUT_S,
        )

        if provider_mode == "gemini" and config.GEMINI_API_KEY:
            provider = GeminiProvider(
                api_key=config.GEMINI_API_KEY,
                model=config.GEMINI_MODEL,
                timeout=config.GEMINI_TIMEOUT_S,
            )
        elif provider_mode == "auto" and config.GEMINI_API_KEY:
            gemini = GeminiProvider(
                api_key=config.GEMINI_API_KEY,
                model=config.GEMINI_MODEL,
                timeout=config.GEMINI_TIMEOUT_S,
            )
            provider = FallbackProvider(primary=gemini, secondary=ollama)
        else:
            provider = ollama

        # Call LLM directly for plain text (not JSON routing)
        system_prompt = config.agent_personality()

        # Direct call to Ollama for plain text response
        if hasattr(provider, 'base_url'):
            # OllamaProvider - call directly for text
            url = f"{provider.base_url}/api/generate"
            payload = json.dumps({
                "model": provider.model,
                "prompt": query,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "num_ctx": 1024,
                    "temperature": 0.7,
                    "num_predict": 150,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=provider.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            text = data.get("response", "").strip()
            if not text:
                return ActionResult(
                    ok=True,
                    spoken=f"No tengo una respuesta para eso, {config.agent_address()}.",
                )

            logger.info("general_qa response: %s", text[:100])
            return ActionResult(ok=True, spoken=text)

        else:
            # Gemini/Fallback - use resolve with a special prompt
            result = provider.resolve(
                f"Respondé esta pregunta directamente (no como JSON, solo texto plano):\n{query}",
                system_prompt
            )
            text = result.get("text", result.get("response", ""))
            if not text:
                return ActionResult(
                    ok=True,
                    spoken=f"No tengo una respuesta para eso, {config.agent_address()}.",
                )

            logger.info("general_qa response: %s", text[:100])
            return ActionResult(ok=True, spoken=text)

    except Exception as exc:
        logger.error("general_qa failed: %s", exc)
        return ActionResult(
            ok=True,
            spoken=f"Lo lamento, {config.agent_address()}, no puedo responder eso ahora.",
        )


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def stream_general_qa(intent: Intent, session: object, speak_fn) -> ActionResult:
    """Like handle_general_qa, but speaks each sentence as it's generated.

    Streams tokens from Ollama (stream=True) instead of waiting for the full
    response, buffering until a sentence boundary (.!?) and calling
    ``speak_fn`` immediately for that sentence — the reply starts playing
    seconds before the model finishes generating the rest, instead of after.

    Only wired for the Ollama path: config.LLM_PROVIDER == "gemini" callers
    should keep using handle_general_qa (Gemini's HTTP streaming shape is
    different and isn't implemented here — falling back to non-streaming for
    that path is intentional, not an oversight).

    Returns an ActionResult with spoken="" (text was already spoken
    incrementally via speak_fn) so the caller doesn't speak it a second time.
    """
    query = intent.entities.get("query", "")
    if not query:
        speak_fn(f"No recibí la pregunta, {config.agent_address()}.")
        return ActionResult(ok=False, spoken="")

    import json
    import urllib.error
    import urllib.request

    system_prompt = config.agent_personality()
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    payload = json.dumps({
        "model": config.INTERPRETER_LLM_MODEL,
        "prompt": query,
        "system": system_prompt,
        "stream": True,
        "options": {
            "num_ctx": 1024,
            "temperature": 0.7,
            "num_predict": 150,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )

    buffer = ""
    full_text_parts: list[str] = []
    try:
        with urllib.request.urlopen(req, timeout=config.OLLAMA_TIMEOUT_S) as resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                token = chunk.get("response", "")
                buffer += token
                # Speak complete sentences as soon as they're ready; keep any
                # trailing partial sentence buffered for the next token(s).
                parts = _SENTENCE_END.split(buffer)
                if len(parts) > 1:
                    for sentence in parts[:-1]:
                        sentence = sentence.strip()
                        if sentence:
                            speak_fn(sentence)
                            full_text_parts.append(sentence)
                    buffer = parts[-1]
                if chunk.get("done"):
                    break
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.error("stream_general_qa failed: %s", exc)
        if not full_text_parts:
            speak_fn(f"Lo lamento, {config.agent_address()}, no puedo responder eso ahora.")
        return ActionResult(
            ok=bool(full_text_parts),
            spoken="",
            data={"response": " ".join(full_text_parts)},
        )

    remainder = buffer.strip()
    if remainder:
        speak_fn(remainder)
        full_text_parts.append(remainder)

    if not full_text_parts:
        speak_fn(f"No tengo una respuesta para eso, {config.agent_address()}.")
        return ActionResult(ok=True, spoken="")

    logger.info("stream_general_qa response: %s", " ".join(full_text_parts)[:100])
    return ActionResult(
        ok=True,
        spoken="",
        data={"response": " ".join(full_text_parts)},
    )
