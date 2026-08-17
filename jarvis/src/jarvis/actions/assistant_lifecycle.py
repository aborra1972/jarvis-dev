"""Assistant lifecycle executor (PR4, task 4.7).

Design (binding: single location): power_off_self lives ONLY here and is
golden-gated + 15s-confirmed by the orchestrator; the executor only logs and
acknowledges. handle_help enumerates the 17-command allowlist. handle_general_qa
provides direct LLM responses for general knowledge questions.
"""

from __future__ import annotations

import logging

from jarvis.actions import base
from jarvis import config
from jarvis.interpreter.schema import ALLOWED_INTENTS, Intent
from jarvis.orchestrator.contracts import ActionResult

logger = logging.getLogger("jarvis.actions")


def power_off_self(intent: Intent, session: object) -> ActionResult:
    base.log("power_off_self")
    return ActionResult(ok=True, spoken="Muy bien, señor. Me apago.")


def handle_help(intent: Intent, session: object) -> ActionResult:
    commands = ", ".join(sorted(ALLOWED_INTENTS - {"unknown"}))
    return ActionResult(ok=True, spoken=f"A su disposición, señor. Puedo: {commands}")


def handle_general_qa(intent: Intent, session: object) -> ActionResult:
    """Answer a general knowledge question using the LLM directly.

    Routes through Ollama/Gemini depending on config, returns the response
    as spoken text for TTS synthesis.
    """
    query = intent.entities.get("query", "")
    if not query:
        return ActionResult(ok=False, spoken="No recibí la pregunta, señor.")

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
        system_prompt = (
            "Sos un asistente virtual útil y amigable. Respondé en español rioplatense, "
            "breve y directo. Máximo 2-3 oraciones. No uses markdown ni formato especial."
        )

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
                return ActionResult(ok=True, spoken="No tengo una respuesta para eso, señor.")

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
                return ActionResult(ok=True, spoken="No tengo una respuesta para eso, señor.")

            logger.info("general_qa response: %s", text[:100])
            return ActionResult(ok=True, spoken=text)

    except Exception as exc:
        logger.error("general_qa failed: %s", exc)
        return ActionResult(ok=True, spoken="Lo lamento, señor, no puedo responder eso ahora.")
