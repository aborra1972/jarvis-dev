<p align="center">
  <img src="jarvis-banner.svg" alt="J.A.R.V.I.S. — Voice Assistant for Linux" width="100%">
</p>

# J.A.R.V.I.S. — Asistente de Voz Local para Linux

Asistente de voz 100% local para desarrollo, inspirado en el JARVIS de Marvel.
Escucha tu wake word "jarvis", transcribe con Whisper, interpreta comandos en
español rioplatense, y ejecuta acciones — todo sin enviar datos a la nube.

## Características

- **Wake word personalizado**: wav2vec2-XLSR + LogisticRegression entrenado con tu voz argentina (~350ms)
- **STT offline**: whisper.cpp (small/medium) — nunca envía audio a internet
- **TTS neural**: Edge TTS (es-MX-JorgeNeural) con fallback offline Piper
- **4 dominios de acción**: sistema, archivos, web, OpenCode
- **Seguridad**: comandos destructivos piden confirmación por voz
- **Interruptor por señal**: `jarvis off`/`jarvis on` con SIGUSR1/SIGUSR2
- **GUI GTK3**: panel de control flotante con botón on/off, slider de sensibilidad, logs
- **Privacidad total**: todo queda en tu máquina

## Requisitos del sistema

### Software

| Requisito | Versión mínima | Verificar |
|-----------|---------------|-----------|
| Linux Mint / Ubuntu | 22.04+ | `lsb_release -a` |
| Python | 3.12+ | `python3 --version` |
| pip | 22+ | `pip --version` |
| Git | 2.30+ | `git --version` |
| Audio (PipeWire/PulseAudio) | — | `pactl info` |
| `paplay` | — | `which paplay` |
| `gst-launch-1.0` | — | `which gst-launch-1.0` |

### Dependencias del sistema

```bash
# Ubuntu / Linux Mint
sudo apt install python3.12 python3.12-venv python3-pip \
  git alsa-utils pulseaudio pipewire \
  libgstreamer1.0-dev gstreamer1.0-plugins-base \
  libgirepository1.0-dev gir1.2-gtk-3.0 \
  python3-gi python3-gi-cairo gir1.2-gtkspell3-3.0
```

### Hardware mínimo

- **Micrófono**: USB o integrado (cualquier micrófono funciona)
- **Altavoces/auriculares**: para la respuesta por voz
- **RAM**: 4GB mínimo, 8GB recomendado (whisper + torch ~3GB)
- **Disco**: ~3GB para modelos y dependencias

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/aborra1972/jarvis-dev.git
cd jarvis-dev
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python3.12 -m venv jarvis/.venv
source jarvis/.venv/bin/activate
pip install -e ./jarvis
```

Esto instala: torch, transformers, onnxruntime, sounddevice, edge-tts, numpy, scipy, openwakeword.

### 3. Verificar que whisper.cpp está compilado

```bash
ls spike/whisper.cpp/build/bin/whisper-cli
ls spike/ggml-small.bin
```

Si falta, compilá whisper.cpp desde `spike/` (ver `spike/` para recetas).

### 4. Instalar Ollama (cerebro LLM)

Ollama es el cerebro de Jarvis para interpretar comandos. Instalación sin sudo:

```bash
# Instalar Ollama en ~/.local/bin (sin sudo)
curl -fsSL https://ollama.com/install.sh | sh

# Iniciar el servidor
~/.local/bin/ollama serve &

# Descargar el modelo qwen2.5:3b (~1.9GB, optimizado para voz)
~/.local/bin/ollama pull qwen2.5:3b
```

Verificar:

```bash
~/.local/bin/ollama list          # Debe mostrar qwen2.5:3b
curl http://localhost:11434/api/tags  # API del servidor
```

**Nota**: El modelo 3B es suficiente para routing de intents (1.4s por comando).
Si preferís más precisión, podés usar `qwen2.5:7b` (~4.7GB, ~3.5s por comando).

### 5. Verificar la instalación

```bash
# Test de importación
python -m jarvis --help

# Test de audio
python -c "import sounddevice; print(sounddevice.query_devices())"
```

### 5. Verificar el wake word entrenado

```bash
ls spike/models/jarvis_wake.onnx
```

Si falta, seguí la guía en `jarvis/docs/wake-word-training.md`.

## Uso rápido

### Desde el escritorio (recomendado)

1. Hacé doble clic en **J.A.R.V.I.S.** del escritorio
2. Hacé clic en **⏻ ENCENDER**
3. Esperá a que diga "Buen día, señor"
4. Decí **"JARVIS"** para activarlo
5. Decí tu comando (ej: "abrí la terminal")

### Desde terminal

```bash
source jarvis/.venv/bin/activate
jarvis start    # Iniciar el asistente
jarvis off      # Apagar (mic liberado, no escucha)
jarvis on       # Reanudar escucha
jarvis clean    # Limpiar logs y audio temporal
```

### Desde otra terminal (señales)

```bash
# Apagar
kill -SIGUSR1 $(cat ~/.local/state/jarvis/jarvis.pid)

# Encender
kill -SIGUSR2 $(cat ~/.local/state/jarvis/jarvis.pid)
```

## Comandos de voz

### Sistema

| Comando | Acción |
|---------|--------|
| "abrí la terminal" | Abre gnome-terminal |
| "abrí firefox" | Abre Firefox |
| "abrí el explorador" | Abre Nemo (file manager) |
| "abrí libreoffice" | Abre LibreOffice |
| "cerrá linux" | Apaga la máquina (pide confirmación) |
| "reiniciá linux" | Reinicia la máquina (pide confirmación) |
| "apagate" | Jarvis se apaga |

### Archivos

| Comando | Acción |
|---------|--------|
| "creá una carpeta llamada X" | Crea directorio |
| "borrá el archivo X" | Elimina archivo (pide confirmación) |

### Web

| Comando | Acción |
|---------|--------|
| "buscá X en internet" | Busca en Google |
| "abrí [url]" | Abre URL en navegador |

### Asistente

| Comando | Acción |
|---------|--------|
| "¿qué podés hacer?" | Lista de comandos disponibles |
| "mostrá el estado" | Estado del proyecto activo |
| "ayuda" | Muestra ayuda |

### Flujo de uso

```
Tú:  "JARVIS"
     [sonido de wake detectado]
Tú:  "abrí la terminal"
Jarvis: "Abriendo la terminal, señor"
     [se abre gnome-terminal]
Tú:  "JARVIS"
Tú:  "cerrá linux"
Jarvis: "¿Confirmo el apagado, señor?"
Tú:  "sí"
Jarvis: "Apagando, señor"
```

## Panel de control (GUI)

```
┌─────────────────────────────┐
│  J.A.R.V.I.S.         v1.0 │
│  Asistente de Voz Local     │
├─────────────────────────────┤
│  ● ACTIVO                   │
│  Escuchando 'JARVIS'...     │
├─────────────────────────────┤
│  Sensibilidad Wake Word     │
│  Baja ← → Alta              │
│           0.50              │
│  ═══════════●═══════════    │
├─────────────────────────────┤
│  📖 Comandos    │  📋 Logs  │
├─────────────────────────────┤
│  Actividad reciente         │
│  [14:30:01] Jarvis iniciado │
│  [14:30:05] Wake detectado  │
└─────────────────────────────┘
```

### Botones

- **⏻ ENCENDER / APAGAR**: Inicia o detiene Jarvis
- **📖 Comandos**: Abre la ventana de ayuda con todos los comandos
- **📋 Logs**: Muestra los logs de actividad reciente

### Slider de sensibilidad

- **Baja (0.1-0.3)**: Solo detecta con pronunciación muy clara
- **Media (0.4-0.6)**: Balance recomendado
- **Alta (0.7-0.9)**: Detecta fácil pero puede activarse con ruido

## Configuración

Las opciones están en `jarvis/src/jarvis/config.py`:

```python
# Wake word
WAKE_ENGINE = "xslr"           # "xslr" (custom) o "openwakeword"
WAKE_THRESHOLD = 0.5           # Sensibilidad (0.1-0.9)
WAKE_XLSR_MODEL = SPIKE / "models" / "jarvis_wake.onnx"

# Audio
AUDIO_SAMPLE_RATE = 16000
AUDIO_SILENCE_MS = 800         # Tiempo de corte por silencio

# TTS
TTS_ENGINE = "edge"            # "edge" (neural) o "piper" (offline)
EDGE_VOICE = "es-MX-JorgeNeural"

# STT
WHISPER_MODEL = SPIKE / "ggml-small.bin"
WHISPER_BEAM = 1               # 1=rápido, 5=preciso

# Apps permitidas
ALLOWED_APPS = {"firefox", "terminal", "gnome-terminal", "nemo", ...}
```

### Cambiar la voz

```python
EDGE_VOICE = "es-MX-DaliaNeural"   # femenina
EDGE_VOICE = "es-MX-JorgeNeural"   # masculina (default)
EDGE_VOICE = "es-AR-TomasNeural"   # argentino
```

## Wake word personalizado

El wake word fue entrenado con tu pronunciación argentina de "jarvis".

### Métricas del modelo

- **Recall**: 96.7% (detecta "jarvis" 97 de 100 veces)
- **Falsos positivos**: 0% en validación
- **Latencia**: ~354ms por ventana de 2s

### Re-entrenar

Si Jarvis no te detecta bien:

```bash
# 1. Grabar positivos (decí "jarvis" ~30 veces)
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/grabar_wake.py pos -n 30

# 2. Grabar negativos (~20 veces)
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/grabar_wake.py neg -n 20

# 3. Extraer embeddings
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/extraer_xlsr.py

# 4. Entrenar y exportar
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/entrenar_clasificador.py --export-onnx

# 5. Copiar modelo
cp /tmp/opencode/train/modelo_wake/clasificador.onnx spike/models/jarvis_wake.onnx
```

## Tests

```bash
source jarvis/.venv/bin/activate
pytest jarvis/tests -q                  # suite unitaria (541 tests, sin hardware)
pytest jarvis/tests/e2e -m e2e          # e2e con binarios reales
```

## Arquitectura

```
spike/                  whisper.cpp / piper / modelos / binarios
jarvis/src/jarvis/
  config.py             paths, allowlists, parámetros de audio, Ollama
  __main__.py           python -m jarvis entry point
  cli.py                jarvis start/off/on/clean
  audio/
    wake.py             wav2vec2-XLSR + OpenWakeWord
    capture.py          sounddevice + SilenceVAD
    stt.py              whisper.cpp STT
    tts.py              Edge TTS + PiperTTS
    pipeline.py         UtteranceCapture, PiperSpeaker, MicSwitch
    playback.py         paplay / gst-launch
  interpreter/
    normalize.py        normalización rioplatense (voseo → infinitivo)
    golden.py           gate determinístico (destructivos + fast-path)
    schema.py           15 comandos, validación de entidades
    llm.py              OllamaProvider (HTTP directo a localhost:11434)
  orchestrator/
    loop.py             FSM: wake → listen → interpret → execute → speak
    session.py          estado persistente (session + off switch)
    confirm.py          confirmación destrucción por voz
    supervisor.py       Clock, watchdog
  actions/
    opencode.py         abrir repos en OpenCode
    system.py           abrir apps del sistema
    files.py            crear/editar archivos
    web.py              buscar / abrir URLs
jarvis_gui.py           GUI GTK3 (panel de control)
launch_jarvis.sh        launcher (system python3 para GTK)
MANUAL_USUARIO.md       manual completo del usuario
```

### Flujo de datos

```
Micrófono → sounddevice (16kHz mono)
  → wav2vec2-XLSR detecta "jarvis" (~350ms)
  → Whisper transcribe a texto (~4s)
  → Normalizador rioplatense ("abrí" → "abrir")
  → Golden gate: matchea patrón regex (destructivos)
  → Ollama (qwen2.5:3b): intent routing (~1.4s, local)
  → Executor ejecuta la acción
  → Edge TTS sintetiza respuesta
  → paplay reproduce audio
```

## Documentación

- **Manual completo**: `MANUAL_USUARIO.md`
- **Comandos**: `jarvis/docs/comandos_jarvis.md`
- **Entrenamiento wake word**: `jarvis/docs/wake-word-training.md`

## Solución de problemas

### Jarvis no detecta "jarvis"
1. Bajá la sensibilidad a 0.3-0.4
2. Grabá más muestras positivas
3. Verificá micrófono: `arecord -l`

### No hay audio
1. Verificá dispositivos: `arecord -l` y `aplay -l`
2. Reiniciá audio: `pulseaudio -k && pulseaudio --start`

### "No entiendo" a todo
Verificá que `ALLOWED_APPS` en `config.py` incluya las apps que querés abrir.
Si el problema persiste, verificá que Ollama esté corriendo:
```bash
curl http://localhost:11434/api/tags
```

### Ollama no responde
1. Iniciar el servidor: `~/.local/bin/ollama serve &`
2. Verificar: `~/.local/bin/ollama list`
3. Si el modelo no está: `~/.local/bin/ollama pull qwen2.5:3b`

### El panel no responde
Cerrá y volvé a abrir. Verificá que no haya otro proceso jarvis corriendo:
```bash
ps aux | grep jarvis
kill -9 <PID>  # si hay uno huérfano
```

## Licencia

Proyecto personal — ver repositorio para detalles.

---

*J.A.R.V.I.S. — Just A Rather Very Intelligent System*
*Versión 1.0 — Agosto 2026*
