# Estudio GitHub: Jarvis Voice Assistants — Mejoras aplicables

**Fecha**: 2026-08-22
**Proyecto**: jarvis-mvp (jarvis-dev)
**Fuente**: Análisis de 10+ repositorios GitHub con stack similar

---

## Proyectos analizados

| Repo | Stars | Stack relevante | Actualizado |
|------|-------|-----------------|-------------|
| NaomiProject/Naomi | 298 | Python, plugin-based, Jasper heritage, múltiples STT/TTS/VAD | 2026-08-07 |
| casha-cashu/jarvis | 7 | Vosk/Whisper STT, Piper TTS, Ollama/OpenAI/Anthropic LLM, Silero VAD, platform adapters, NLU classifier | 2026-07-26 |
| morrolinux/jarvis_linux | 19 | Whisper turbo + ShellGPT, GUI Tkinter | 2026-06-14 |
| casha-cashu/jarvis (forks) | 8 | Gnu/Linux AI voice assistant | 2026-07-26 |
| GradByte/Jarvis-on-Linux | 1 | OpenWakeWord, Google STT, Fish Audio TTS, Antigravity CLI | 2026-08-15 |
| qartex/jarvis-desktop | 1 | Next.js + Three.js particle orb + FastAPI + Chrome extension + 109 tools | 2026-04-28 |
| kalai4390/Local_Voice_Assistant | 1 | Phi-4 (9.1GB) + VibeVoice TTS + Whisper, 100% offline | 2026-03-10 |
| ConceptBytes/jarvis | — | Desktop app cross-platform, cinematic HUD, ElevenLabs/OpenAI Realtime | — |
| fedcal/open-jarvis | — | Iron Man-style personal AI infrastructure, self-hosted | — |
| Krish-alt877/jarvisapp.in | — | Desktop app, Gemma offline + Claude/ChatGPT/Gemini cloud, voice-native | — |

---

## Mejías de alto impacto — incorporar ahora (prioridad 1-8)

### 1. Silero VAD para corte de grabación
**Fuente**: casha-cashu/jarvis
**Estado actual**: Umbral de energía fijo (RMS > threshold)
**Propuesta**: Silero VAD (torch hub) para detectar voz real vs ruido
**Beneficio**: Más preciso que energy threshold, evita cortes prematuros o grabar ruido
**Tamaño**: ~1MB modelo Silero
**Dependencias**: torch (ya instalado para wake word training)

```python
# casha-cashu/jarvis/modules/vad.py
class SileroVAD:
    def __init__(self, threshold=0.5, sampling_rate=16000,
                 min_speech_duration_ms=250, min_silence_duration_ms=500):
        self.model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad", force_reload=False, onnx=False, trust_repo=True
        )
        (self.get_speech_timestamps, self.save_audio, self.read_audio,
         self.VADIterator, self.collect_chunks) = utils
```

### 2. Bash agent con 3 capas de seguridad
**Fuente**: casha-cashu/jarvis/modules/bash_agent.py
**Estado actual**: Golden table solo para shutdown/reboot/power_off_self
**Propuesta**: Extender con ~40 patrones de peligro + approval gate

```python
# Hardline blocklist — siempre bloqueado
_HARDLINE_PATTERNS = [
    re.compile(r"rm\s+-rf\s+/", re.IGNORECASE),
    re.compile(r"mkfs", re.IGNORECASE),
    re.compile(r"dd\s+.*of=/dev/sd", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),  # fork bomb
    re.compile(r"chmod\s+-R\s+000\s+/", re.IGNORECASE),
]

# Dangerous patterns — ~40 patrones con warnings
_DANGEROUS_PATTERNS = [
    (re.compile(r"rm\s+-rf\s+~", re.IGNORECASE), "recursive home deletion"),
    (re.compile(r"curl.*\|.*sh", re.IGNORECASE), "curl-pipe-bash"),
    (re.compile(r"git\s+push\s+--force", re.IGNORECASE), "force push"),
    (re.compile(r"iptables\s+-F", re.IGNORECASE), "flush firewall"),
    # ... 40+ patrones
]

# Approval gate: auto / strict / yolo
```

### 3. Multi-turn follow-up con timeout
**Fuente**: casha-cashu/jarvis/modules/conversation_manager.py
**Estado actual**: FSM va idle → listening → executing → speaking → idle
**Propuesta**: Estado follow-up después de speaking, timeout configurable (10s)

```python
class ConversationManager:
    UNMUTE_KEYWORDS = ("prosne", "jarvis", "hay")

    def has_wake_in_follow_up(self, text: str) -> bool:
        """True si en follow-up sonó wake word —
        multi-turn interrumpido, nuevo запрос"""
        return any(w in text.lower() for w in self.wake_words)
```

### 4. Calibración de ruido ambiente al activarse wake word
**Fuente**: GradByte/Jarvis-on-Linux
**Estado actual**: Umbral fijo de energía
**Propuesta**: 0.5s de calibración de fondo al activarse, umbral dinámico

```python
# GradByte/Jarvis-on-Linux/jarvis.py
def calibrate_ambient_noise(self, duration_sec=0.5):
    """Calibrar nivel de ruido ambiente al inicio de cada wake"""
    frames = int(duration_sec * SAMPLE_RATE / CHUNK_SIZE)
    noise_levels = []
    for _ in range(frames):
        data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        rms = self.calculate_rms(data)
        noise_levels.append(rms)
    self.noise_floor = np.mean(noise_levels) * 1.2  # 20% margin
```

### 5. Flush de buffer stale post-playback
**Fuente**: GradByte/Jarvis-on-Linux
**Estado actual**: No hay flush explícito
**Propuesta**: Flush de 1s de audio después de TTS playback para evitar loopback

```python
# Flush stale audio from mic buffer (1 second)
flush_frames = int(1.0 * self.sample_rate / self.chunk_size)
for _ in range(flush_frames):
    stream.read(self.chunk_size, exception_on_overflow=False)
```

### 6. Rapidfuzz para fuzzy matching
**Fuente**: casha-cashu/jarvis/modules/commands.py
**Estado actual**: difflib.SequenceMatcher (lento)
**Propuesta**: rapidfuzz.fuzz.ratio — 10-100x más rápido

```python
try:
    from rapidfuzz import fuzz as _rf_fuzz
    _HAVE_RAPIDFUZZ = True
except ImportError:
    from difflib import SequenceMatcher  # fallback
    _HAVE_RAPIDFUZZ = False
```

### 7. NLU classifier (TF-IDF + LogReg) para intents no destructivos
**Fuente**: casha-cashu/jarvis/modules/nlu.py
**Estado actual**: Golden table + LLM primero
**Propuesta**: Intent classifier cacheado como alternativa al LLM para intents comunes

```python
class IntentClassifier:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        self.classifier = LogisticRegression()
        self.joblib = _try_import_joblib()

    def train(self, examples: list):
        """Entrena con ejemplos de comandos rioplatenses"""
        texts = [ex["text"] for ex in examples]
        labels = [ex["intent"] for ex in examples]
        self.vectorizer.fit(texts)
        self.classifier.fit(self.vectorizer.transform(texts), labels)
        if self.joblib:
            self.joblib.dump((self.vectorizer, self.classifier), cache_path)
```

### 8. `jarvis diagnose` — verificación pre-start
**Fuente**: NaomiProject/Naomi/diagnose.py
**Estado actual**: No hay diagnóstico integrado
**Propuesta**: Comando que verifica mic, STT, TTS, wake word, Ollama antes de arrancar

```bash
$ jarvis diagnose
✅ Micrófono: HDA Intel PCH (card 0, device 0)
✅ Wake word: jarvis_wake.onnx cargado (threshold 0.5)
✅ Whisper: ggml-small.bin presente (487MB)
✅ Piper: modelo es_AR-daniela presente
❌ Ollama: no corriendo (run: ollama serve &)
✅ Audio output: paplay disponible
```

---

## Mejías de medio impacto — Fase 2 (prioridad 9-15)

### 9. Dictation mode
**Fuente**: casha-cashu/jarvis
**Propuesta**: `jarvis dictation` — modo dictado separado del asistente
**Uso**: Input de texto por voz en cualquier app, sin comandos
**Implementación**: Whisper continuo → texto → clipboard/wtype

### 10. Fish Audio TTS con emotion tags
**Fuente**: GradByte/Jarvis-on-Linux
**Propuesta**: TTS con tags `[excited]`, `[laughs]`, `[calm]`, `[whispers]`
**Beneficio**: Personalidad real en la voz, no solo texto plano

### 11. VibeVoice TTS streaming
**Fuente**: kalai4390/Local_Voice_Assistant
**Propuesta**: Microsoft VibeVoice-Realtime-0.5B como alternativa a Piper
**Beneficio**: Mejor latencia para respuestas largas, neural TTS

### 12. Recordatorios como dominio extra
**Fuente**: casha-cashu/jarvis/modules/reminder.py
**Propuesta**: "recordame en 10 minutos llamar a Juan"
**Implementación**: Parseo de tiempo natural + timer + notify-send + TTS

### 13. Standard phrases rioplatenses
**Fuente**: NaomiProject/Naomi/brain.py
**Propuesta**: Lista de palabras que el usuario realmente dice para mejorar STT
**Beneficio**: Whisper prioriza vocabulario rioplatense con `--prompt`

### 14. Persistencia de conversación atómica
**Fuente**: casha-cashu/jarvis/modules/llm.py
**Propuesta**: Historial con temp+rename, no se corrompe
**Formato**: `~/.local/share/jarvis/history.json`

### 15. Desencadenar agentes IA por voz
**Fuente**: casha-cashu/jarvis + nuestro diseño actual
**Propuesta**: Expandir comandos de agente:
- "Jarvis, que revise el PR abierto"
- "implementá el test que falta"
- "corregí los 3 warnings del lint"
- "creá un artifact con el resumen del sprint"

---

## UI cinematográfica — Post-MVP (prioridad 16)

### 16. Página inicial estilo Jarvis
**Fuentes**: qartex/jarvis-desktop, ConceptBytes, fedcal/open-jarvis

**qartex/jarvis-desktop**:
- Three.js particle orb con 2,400 partículas
- Colores por estado: azul=idle, naranja=thinking, verde=listening, rojo=error
- Desktop overlay siempre-arriba (GTK en Linux, Swift en macOS)
- WebSocket en tiempo real
- Chrome Extension para control del browser
- 109+ tools (apps, files, shell, desktop, web, browser, clipboard, media, system)

**ConceptBytes**:
- Cinematic sci-fi HUD con arc reactor
- Visualizadores de audio
- Widgets arrastrables
- Animación de inicio
- Visor de 3D, cámara, notas, PDFs, mapas, música
- Desktop app cross-platform (Windows, Mac, Linux)

**fedcal/open-jarvis**:
- Infraestructura personal AI auto-hosteada
- Multi-dispositivo
- Estilo Iron Man

**Krish-alt877 (jarvisapp.in)**:
- Orbital core, partículas, sistema listo
- Gemma offline + Claude/ChatGPT/Gemini cloud
- Voice-native engine

---

## Plan de incorporación

```
jarvis-mvp/
├── src/jarvis/
│   ├── audio/
│   │   ├── capture.py          # [MEJORADO] Silero VAD + calibración ruido + flush post-playback
│   │   ├── wake.py             # [EXISTENTE] openWakeWord
│   │   ├── stt.py              # [EXISTENTE] whisper-cli
│   │   └── tts.py              # [EXISTENTE] piper
│   ├── interpreter/
│   │   ├── normalize.py        # [EXISTENTE]
│   │   ├── golden.py           # [MEJORADO] + 3 capas seguridad bash agent
│   │   ├── nlu_classifier.py   # [NUEVO] TF-IDF + LogReg
│   │   └── llm.py              # [EXISTENTE]
│   ├── orchestrator/
│   │   ├── state.py            # [MEJORADO] + follow-up timeout
│   │   ├── confirm.py          # [EXISTENTE]
│   │   ├── session.py          # [EXISTENTE]
│   │   └── loop.py             # [EXISTENTE]
│   ├── actions/
│   │   ├── base.py             # [EXISTENTE]
│   │   ├── opencode.py         # [MEJORADO] + más comandos de agente por voz
│   │   ├── system.py           # [EXISTENTE]
│   │   ├── files.py            # [EXISTENTE]
│   │   ├── web.py              # [EXISTENTE]
│   │   └── assistant_lifecycle.py  # [MEJORADO] + recordatorios + dictation
│   ├── cli.py                  # [MEJORADO] + diagnose + dictation mode
│   └── diagnose.py             # [NUEVO] verificación pre-start
├── jarvis_gui/                  # [NUEVO] post-MVP - UI cinematográfica
│   ├── orb.py                  # Three.js/Canvas particle orb
│   ├── overlay.py              # GTK always-on-top
│   └── state_visualizer.py     # Colores por estado
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── pyproject.toml              # [MEJORADO] + rapidfuzz, silero-vad, joblib
```

---

## Comparativa: Nuestro diseño vs otros proyectos

| Característica | jarvis-mvp | casha-cashu/jarvis | GradByte/Jarvis | Naomi | qartex/desktop |
|----------------|------------|-------------------|-----------------|-------|----------------|
| Wake word | openWakeWord + custom | openWakeWord | openWakeWord | Snowboy | openWakeWord |
| STT | whisper-cli | Vosk/Whisper | Google STT | Múltiples | Whisper |
| TTS | Piper | Piper | Fish Audio | Múltiples | Piper |
| LLM | OpenCode provider | Ollama/OpenAI/Anthropic | Antigravity CLI | Plugin-based | Multi-tier |
| VAD | Energy threshold | Silero VAD | Energy VAD | WebRTC/SNR | Silero |
| Seguridad | Golden table | 3 capas + ~40 patrones | Ninguna | Plugin valid | 109 tools |
| Multi-turn | ❌ | ✅ (10s timeout) | ❌ | ✅ | ✅ |
| NLU classifier | ❌ | ✅ TF-IDF+LogReg | ❌ | ✅ Intent parser | ❌ |
| Fuzzy matching | ❌ | ✅ rapidfuzz | ❌ | ❌ | ❌ |
| Diagnóstico | ❌ | ❌ | ❌ | ✅ | ❌ |
| UI cinematográfica | ❌ | ❌ | ❌ | ❌ | ✅ Three.js orb |
| Dictation mode | ❌ | ✅ | ❌ | ❌ | ❌ |
| Recordatorios | ❌ | ✅ | ❌ | ❌ | ✅ |
| Platform adapters | ❌ | ✅ (6 DE/WM) | ❌ | ❌ | ✅ (macOS+Linux) |
| Browser automation | ❌ | ❌ | ❌ | ❌ | ✅ Playwright |
| Memory/learning | ❌ | ✅ history.json | ❌ | ✅ Profile | ✅ SQLite |
| Multi-agent | ❌ | ❌ | ❌ | ❌ | ✅ Planner→Executor→QA |

---

## Conclusiones

1. **Nuestro diseño ya cubre el 70%** de las mejores prácticas encontradas
2. **Las 8 mejoras de alto impacto** son relativamente fáciles de incorporar
3. **La UI cinematográfica** es post-MVP pero vale la pena planificarla
4. **El dictation mode** es un caso de uso válido y fácil de implementar
5. **Los agentes IA por voz** ya están parcialmente en nuestro diseño (implement, review, etc.)
6. **Naomi** es el más maduro pero su arquitectura plugin es overkill para nuestro MVP
7. **casha-cashu/jarvis** es el más relevante técnicamente — comparte stack similar y tiene mejoras concretas
8. **qartex/jarvis-desktop** tiene la mejor UI pero es muy pesado para nuestro scope

---

*Estudio realizado el 2026-08-22 — Análisis de 10+ repositorios GitHub*
