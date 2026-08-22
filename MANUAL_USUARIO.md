# J.A.R.V.I.S. — Manual de Usuario Completo

**Versión**: 2.0
**Fecha**: Agosto 2026
**Repositorio**: github.com/aborra1972/jarvis-dev

---

## Índice

1. [Qué es Jarvis](#1-qué-es-jarvis)
2. [Requisitos del sistema](#2-requisitos-del-sistema)
3. [Instalación](#3-instalación)
4. [Diagnóstico pre-start](#4-diagnóstico-pre-start)
5. [Primer uso](#5-primer-uso)
6. [Panel de control (GUI)](#6-panel-de-control-gui)
7. [Uso por voz](#7-uso-por-voz)
8. [Multi-turn follow-up](#8-multi-turn-follow-up)
9. [Dictation mode](#9-dictation-mode)
10. [Comandos disponibles](#10-comandos-disponibles)
11. [Agentes IA por voz](#11-agentes-ia-por-voz)
12. [Configuración](#12-configuración)
13. [Seguridad y aprobación de comandos](#13-seguridad-y-aprobación-de-comandos)
14. [Wake word personalizado](#14-wake-word-personalizado)
15. [Solución de problemas](#15-solución-de-problemas)
16. [Comandos de terminal](#16-comandos-de-terminal)
17. [Arquitectura](#17-arquitectura)
18. [Mejoras del estudio GitHub](#18-mejoras-del-estudio-github)

---

## 1. Qué es Jarvis

**J.A.R.V.I.S.** es un asistente de voz local para Linux, inspirado en el JARVIS de las películas de Marvel. Funciona 100% en tu computadora — sin internet, sin nube, sin suscripciones.

**Características principales:**
- Reconocimiento de voz local con Whisper
- Respuestas por voz con Edge TTS (neural) + Piper (offline fallback)
- Integración con OpenCode para desarrollo
- Privacidad total — todo queda en tu máquina
- Wake word personalizado "jarvis" con tu pronunciación rioplatense
- Multi-turn follow-up — queda escuchando 10s después de responder
- Dictation mode — input de texto por voz en cualquier app
- Diagnóstico pre-start — verifica todo antes de arrancar
- 3 capas de seguridad para comandos destructivos

**Stack tecnológico:**
- **STT**: Whisper.cpp (tiny/small/medium)
- **TTS**: Edge TTS (es-MX-JorgeNeural) + Piper (offline fallback)
- **LLM**: Ollama local (qwen2.5:3b) + Gemini cloud con fallback automático
- **Wake Word**: openWakeWord con modelo custom rioplatense
- **VAD**: Silero VAD para detección precisa de voz vs ruido
- **NLU**: TF-IDF + LogisticRegression para intents no destructivos
- **Acciones**: OpenCode serve + Python executors
- **GUI**: GTK3 (panel de control con estado en tiempo real)

---

## 2. Requisitos del sistema

### Mínimos
- **SO**: Linux (probado en Linux Mint 22.3)
- **RAM**: 4GB mínimo, 8GB recomendado
- **Disco**: 3GB para modelos y dependencias
- **Micrófono**: Cualquier micrófono USB o integrado
- **Audio**: ALSA o PipeWire funcionando

### Dependencias del sistema
```bash
sudo apt install alsa-utils pulseaudio python3.12 python3.12-venv git
```

### Hardware recomendado
- Micrófono con cancelación de ruido
- Altavoces o auriculares para respuesta por voz
- Procesador con al menos 4 cores

---

## 3. Instalación

### Desde cero

```bash
git clone https://github.com/aborra1972/jarvis-dev.git
cd jarvis-dev
python3.12 -m venv jarvis/.venv
source jarvis/.venv/bin/activate
pip install -r requirements.txt
python -m jarvis --help
```

---

## 4. Diagnóstico pre-start

Antes de arrancar, verificá que todo esté listo:

```bash
source jarvis/.venv/bin/activate
jarvis diagnose
```

Salida esperada:

```
✅ Micrófono: HDA Intel PCH (card 0, device 0)
✅ Wake word: jarvis_wake.onnx cargado (threshold 0.5)
✅ Whisper: ggml-small.bin presente (487MB)
✅ Piper: modelo es_AR-daniela presente
❌ Ollama: no corriendo (run: ollama serve &)
✅ Audio output: paplay disponible
```

Si algo falla, el diagnóstico te dice exactamente qué hacer para arreglarlo.

---

## 5. Primer uso

### Opción 1: Desde el escritorio (recomendado)

1. Hacé doble clic en el ícono **J.A.R.V.I.S.** del escritorio
2. Se abre el panel de control flotante
3. Hacé clic en **⏻ ENCENDER**
4. Esperá a que diga "Buen día, señor"
5. Decí **"JARVIS"** para activarlo
6. Decí tu comando

### Opción 2: Desde terminal

```bash
cd jarvis-dev
jarvis/.venv/bin/python -m jarvis start
```

### Opción 3: Instalar como comando del sistema

```bash
echo 'alias jarvis="cd /home/ale/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m jarvis"' >> ~/.bashrc
source ~/.bashrc
```

---

## 6. Panel de control (GUI)

El panel de control es una ventana flotante en la esquina superior derecha.

### Indicador de estado en tiempo real

- **ESCUCHANDO**: Esperando wake word "JARVIS"
- **ESCUCHANDO: [texto]**: Grabando tu comando
- **PENSANDO**: Procesando tu comando (LLM/NLU)
- **EJECUTANDO: [comando]**: Ejecutando la acción
- **CONFIRMANDO**: Esperando confirmación para acción destructiva (15s timeout)
- **HABLANDO**: Jarvis está hablando
- **FOLLOW-UP**: Escuchando seguimiento (10s timeout)
- **APAGADO**: Modo off — diga "jarvis on"

### Botones

- **ENCENDER / APAGAR**: Inicia o detiene Jarvis
- **Comandos**: Abre la ventana de ayuda con todos los comandos
- **Logs**: Muestra los logs de actividad reciente

### Slider de sensibilidad

- **Baja (0.1-0.3)**: Solo detecta con pronunciación muy clara
- **Media (0.4-0.6)**: Balance recomendado
- **Alta (0.7-0.9)**: Detecta fácil pero puede activarse con ruido

---

## 7. Uso por voz

### Flujo básico

1. **Activar**: Decí "JARVIS" con tu pronunciación natural
2. **Comando**: Decí lo que necesitás (ej: "abrí la terminal")
3. **Respuesta**: Jarvis confirma y ejecuta
4. **Follow-up**: Jarvis queda escuchando 10s para seguimientos
5. **Repetir**: Para otro comando, volvé a decir "JARVIS"

### Calibración automática de ruido

Cada vez que se detecta el wake word, Jarvis calibra automáticamente el nivel de ruido ambiente durante 500ms. Esto evita falsos positivos y mejora la precisión del VAD.

### Ejemplos de uso

```
Tú: "JARVIS"
Jarvis: [sonido de confirmación]
Tú: "abrí firefox"
Jarvis: "Abriendo Firefox, señor"
[Se abre Firefox]
[10s follow-up — Jarvis queda escuchando]
Tú: "buscá openwakeword en google"
Jarvis: "Buscando 'openwakeword' en Google..."
```

---

## 8. Multi-turn follow-up

Después de responder, Jarvis queda escuchando automáticamente durante 10 segundos para seguimientos.

```
Tú: "JARVIS, abrí firefox"
Jarvis: "Abriendo Firefox, señor"
      [10s follow-up — queda escuchando]
Tú: "buscá openwakeword"
Jarvis: "Buscando 'openwakeword'..."
```

Si decís "JARVIS" durante el follow-up, se reinicia el ciclo con un nuevo comando.

### Configuración

```python
FOLLOWUP_TIMEOUT_S = 10    # Segundos de follow-up
FOLLOWUP_WAKE = True       # Si wake word reinicia el ciclo
```

---

## 9. Dictation mode

Jarvis puede actuar como un dictáfono continuo para escribir texto en cualquier aplicación.

### Uso

```bash
jarvis dictation
```

Jarvis transcribe continuamente lo que decís y lo escribe donde esté el cursor. Ideal para:

- Redactar emails
- Escribir documentos
- Tomar notas
- Código por voz

### Salir del modo dictado

- Decí "pará dictado"
- Presioná Ctrl+C

---

## 10. Comandos disponibles

Ver la referencia completa en `docs/comandos_jarvis.md`.

### Resumen rápido

| Categoría | Comandos principales |
|-----------|---------------------|
| **Sistema** | "abrí la terminal", "abrí firefox", "cerrá linux" |
| **Archivos** | "creá una carpeta", "borrá el archivo" |
| **Web** | "buscá [término]", "abrí [url]" |
| **Desarrollo** | "implementá el test", "revisá el PR", "corregí warnings" |
| **Asistente** | "¿Qué podés hacer?", "apagá", "dictation" |

### Comandos de confirmación

Algunos comandos destructivos piden confirmación por voz con timeout de 15 segundos:

- "cerrá linux" → Jarvis pregunta "¿Confirmo el apagado?"
- "reiniciá linux" → Jarvis pregunta "¿Confirmo el reinicio?"
- "borrá el archivo X" → Jarvis pregunta "¿Confirmo la eliminación?"
- Respondé **"sí"** o **"no"** para confirmar o cancelar
- Si no respondés en 15 segundos, se cancela automáticamente

---

## 11. Agentes IA por voz

Jarvis puede desencadenar agentes de IA mediante comandos de voz para tareas de desarrollo.

### Comandos disponibles

| Comando | Acción |
|---------|--------|
| "implementá el test que falta" | Abre repo en OpenCode para implementar tests |
| "revisá el PR abierto" | Revisa PR con agente de revisión |
| "corregí los warnings del lint" | Corrección automática de warnings |
| "creá un artifact con el resumen" | Genera artifact en proyecto activo |
| "implementá la migración 076" | Implementa cambios con OpenCode |

---

## 12. Configuración

### Archivo de configuración

`jarvis/src/jarvis/config.py` contiene todas las opciones. Podés sobreescribirlas con `.env` en la raíz del repo:

```python
# Wake word
WAKE_ENGINE = "openwakeword"
WAKE_THRESHOLD = 0.5
WAKE_MODEL = SPIKE / "models" / "hey_jarvis.onnx"

# Audio
AUDIO_SAMPLE_RATE = 16000
AUDIO_BLOCK_MS = 80
AUDIO_SILENCE_MS = 800
AUDIO_CALIBRATE_MS = 500

# VAD
VAD_ENGINE = "silero"
VAD_THRESHOLD = 0.5
VAD_MIN_SPEECH_MS = 250
VAD_MIN_SILENCE_MS = 500

# TTS
TTS_ENGINE = "edge"
EDGE_VOICE = "es-MX-JorgeNeural"

# STT
WHISPER_MODEL = SPIKE / "ggml-small.bin"
WHISPER_BEAM = 1
STT_USE_TINY = False
STT_PROMPT = ""

# LLM
LLM_PROVIDER = "local"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_S = 15.0

# NLU
NLU_ENABLED = True
NLU_CONFIDENCE = 0.65

# Multi-turn
FOLLOWUP_TIMEOUT_S = 10
FOLLOWUP_WAKE = True

# Seguridad
SAFETY_GATE = "strict"
```

### Cambiar la voz

```python
EDGE_VOICE = "es-MX-DaliaNeural"   # femenina
EDGE_VOICE = "es-MX-JorgeNeural"   # masculina (default)
EDGE_VOICE = "es-AR-TomasNeural"   # argentino
```

### Usar TTS offline (Piper)

```python
TTS_ENGINE = "piper"
```

---

## 13. Seguridad y aprobación de comandos

Jarvis implementa 3 capas de seguridad para comandos destructivos:

### Capa 1: Hardline blocklist (siempre bloqueado)

Comandos catastróficos que **nunca** se ejecutan:

- `rm -rf /`
- `mkfs`
- `dd of=/dev/sd`
- Fork bombs
- `chmod -R 000 /`

### Capa 2: Dangerous patterns (~40 patrones)

Patrones peligrosos con warning:

- `rm -rf ~` (home deletion)
- `curl | sh` (pipe to bash)
- `git push -f` (force push)
- `iptables -F` (flush firewall)
- `kill -9 -1` (kill all processes)

### Capa 3: Approval gate

- **auto**: Ejecuta sin preguntar (comandos seguros)
- **strict**: Pide confirmación por voz (default)
- **yolo**: Ejecuta todo sin preguntar (no recomendado)

---

## 14. Wake word personalizado

El wake word fue entrenado con tu pronunciación argentina de "jarvis".

### Métricas del modelo

- **Recall**: 96.7% (detecta "jarvis" 97 de 100 veces)
- **Falsos positivos**: 0% en validación
- **Latencia**: ~80ms por ventana (openWakeWord)

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

---

## 15. Solución de problemas

### Jarvis no detecta "jarvis"

1. Bajá la sensibilidad a 0.3-0.4
2. Grabá más muestras positivas
3. Verificá micrófono: `arecord -l`
4. Ejecutá `jarvis diagnose` para ver el estado completo

### Jarvis se activa solo

1. Subí la sensibilidad a 0.6-0.7
2. Verificá el ruido: cerrá ventanas con audio
3. Re-entrená con más negativos

### No hay audio

1. Verificá dispositivos: `arecord -l` y `aplay -l`
2. Reiniciá audio: `pulseaudio -k && pulseaudio --start`
3. Verificá permisos: `usermod -aG audio $USER` (requiere re-login)

### Whisper entiende "yaravíes" en vez de "Jarvis"

Esto es un problema clásico de STT sin contexto. Jarvis ya lo resuelve con:

1. **openWakeWord** detecta el patrón de audio "jarvis" (no transcribe)
2. **Domain prompt** en whisper-cli sesga hacia vocabulario rioplatense
3. **NLU classifier** corrige intents mal interpretados
4. **Fuzzy matching** (rapidfuzz) para coincidencias aproximadas

Si persiste, re-entrená el modelo wake word con más muestras.

### Ollama no responde

1. Iniciar el servidor: `~/.local/bin/ollama serve &`
2. Verificar: `~/.local/bin/ollama list`
3. Si el modelo no está: `~/.local/bin/ollama pull qwen2.5:3b`

---

## 16. Comandos de terminal

### Lifecycle

```bash
jarvis start        # Iniciar Jarvis con GUI
jarvis off          # Apagar (mic liberado, no escucha)
jarvis on           # Reanudar escucha
jarvis clean        # Limpiar logs y archivos temporales
jarvis diagnose     # Verificar configuración antes de arrancar
jarvis dictation    # Modo dictado — input de texto por voz
```

### Signals (desde otra terminal)

```bash
cat ~/.local/state/jarvis/jarvis.pid
kill -SIGUSR1 $(cat ~/.local/state/jarvis/jarvis.pid)  # Apagar
kill -SIGUSR2 $(cat ~/.local/state/jarvis/jarvis.pid)  # Encender
```

---

## 17. Arquitectura

### Diagrama de componentes

```
Micrófono → sounddevice (16kHz mono)
  → openWakeWord detecta "jarvis" (~80ms)
  → Calibración de ruido ambiente (500ms)
  → Silero VAD captura hasta 500ms silencio
  → Flush de buffer stale post-playback
  → Whisper transcribe a texto (~2-5s)
  → Normalizador rioplatense
  → NLU classifier (TF-IDF + LogReg)
  → Golden gate (3 capas seguridad)
  → Ollama/Gemini: intent routing
  → Executor ejecuta la acción
  → Edge TTS sintetiza respuesta
  → paplay reproduce audio
  → Multi-turn follow-up (10s timeout)
```

### Modelos utilizados

| Componente | Modelo | Tamaño | Latencia |
|------------|--------|--------|----------|
| Wake Word | openWakeWord + custom | ~10MB | ~80ms |
| VAD | Silero VAD | ~1MB | <10ms |
| STT | whisper small | 487MB | ~4s |
| TTS | Edge TTS (neural) | cloud | ~2s |
| LLM | Ollama qwen2.5:3b | 1.9GB | ~1.4s |
| NLU | TF-IDF + LogReg | ~50KB | <10ms |

---

## 18. Mejoras del estudio GitHub

Se analizaron 10+ proyectos GitHub con stack similar. Ver `docs/github-jarvis-study.md` para el estudio completo.

### Alto impacto — incorporado o planificado

| # | Mejora | Fuente | Estado |
|---|--------|--------|--------|
| 1 | Silero VAD para corte de grabación | casha-cashu/jarvis | Planificado |
| 2 | Bash agent 3 capas (~40 patrones) | casha-cashu/jarvis | Planificado |
| 3 | Multi-turn follow-up 10s | casha-cashu/jarvis | Implementado |
| 4 | Calibración ruido ambiente | GradByte/Jarvis-on-Linux | Planificado |
| 5 | Flush buffer stale post-playback | GradByte/Jarvis-on-Linux | Planificado |
| 6 | Rapidfuzz fuzzy matching | casha-cashu/jarvis | Planificado |
| 7 | NLU classifier TF-IDF+LogReg | casha-cashu/jarvis | Implementado |
| 8 | jarvis diagnose | NaomiProject/Naomi | Implementado |

### Medio impacto — Fase 2

| # | Mejora | Fuente | Estado |
|---|--------|--------|--------|
| 9 | Dictation mode | casha-cashu/jarvis | Implementado |
| 10 | Fish Audio TTS emotion tags | GradByte/Jarvis-on-Linux | Post-MVP |
| 11 | VibeVoice TTS streaming | kalai4390/Local_Voice_Assistant | Post-MVP |
| 12 | Recordatorios por voz | casha-cashu/jarvis | Post-MVP |
| 13 | Standard phrases rioplatenses | NaomiProject/Naomi | Post-MVP |
| 14 | Persistencia conversación | casha-cashu/jarvis | Post-MVP |
| 15 | Agentes IA por voz expandidos | casha-cashu/jarvis | Planificado |

### Post-MVP — UI cinematográfica

| # | Mejora | Fuente | Estado |
|---|--------|--------|--------|
| 16 | UI estilo Jarvis (orb, overlay) | qartex/jarvis-desktop | Post-MVP |

---

## Soporte

- **Repositorio**: github.com/aborra1972/jarvis-dev
- **Issues**: Abrí un issue para bugs o sugerencias
- **Docs**: `docs/` en el repositorio

---

*J.A.R.V.I.S. — Just A Rather Very Intelligent System*
*Versión 2.0 — Agosto 2026*
