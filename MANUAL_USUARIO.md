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
- Modo conversación — respondé seguimientos sin repetir "jarvis" (8s configurables)
- Dictation mode — input de texto por voz en cualquier app
- Diagnóstico pre-start — verifica todo antes de arrancar
- Detección robusta al ruido — Silero VAD ONNX + calibración al wake
- 3 capas de seguridad para comandos destructivos

**Stack tecnológico:**
- **STT**: Whisper.cpp (tiny/small/medium)
- **TTS**: Edge TTS (es-MX-JorgeNeural) + Piper (offline fallback)
- **LLM**: Ollama local (qwen2.5:3b) + Gemini cloud con fallback automático
- **Wake Word**: openWakeWord / XLSR con modelo custom rioplatense
- **VAD**: Silero VAD ONNX (offline, sin nube)
- **NLU**: TF-IDF + LogisticRegression para sugerencias al no entender
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
4. **Follow-up**: Jarvis queda escuchando unos segundos para seguimientos
5. **Repetir**: Para otro comando, volvé a decir "JARVIS"

### Calibración automática de ruido

Cada vez que se detecta el wake word, Jarvis calibra automáticamente el nivel de ruido ambiente durante 500ms. Esto evita falsos positivos y mejora la precisión del VAD.

### Detección robusta al ruido

Jarvis combina tres mecanismos para escucharte bien incluso con ruido de fondo:

1. **Silero VAD ONNX**: red neuronal de detección de voz (offline, sin nube). Separa tu voz del ruido ambiente y corta la grabación cuando dejás de hablar.
2. **Calibración de ruido al wake**: al detectar "jarvis", mide el ruido ambiente 500ms y sube el umbral (ruido × 1.2) para no confundir ruido con voz.
3. **Flush de buffer post-respuesta**: cuando Jarvis termina de hablar, descarta ~1s de audio residual para que su propia voz no re-dispare el wake word en el siguiente ciclo.

### Ejemplos de uso

```
Tú: "JARVIS"
Jarvis: [sonido de confirmación]
Tú: "abrí firefox"
Jarvis: "Abriendo Firefox, señor"
[Se abre Firefox]
[beep suave — queda escuchando para seguimientos]
Tú: "buscá openwakeword en google"
Jarvis: "Buscando 'openwakeword' en Google..."
```

---

## 8. Multi-turn follow-up (modo conversación)

Después de ejecutar un comando con éxito, Jarvis queda escuchando automáticamente durante una ventana configurable (8 segundos por defecto) para seguimientos sin repetir el wake word.

```
Tú: "JARVIS, abrí firefox"
Jarvis: "Abriendo Firefox, señor"
      [beep suave — queda escuchando 8s]
Tú: "ahora abrí spotify"
Jarvis: "Abriendo Spotify, señor"
      [beep suave — la ventana se renueva otros 8s]
```

Si no decís nada en la ventana, vuelve a requerir "jarvis" normalmente.
La ventana solo se arma tras un comando **exitoso**: si Jarvis no entendió o
rechazó el comando, no queda escuchando de más.

### Configuración

```python
CONVERSATION_WINDOW_S = 8.0    # Segundos de follow-up sin wake word; 0 = off
BARGE_IN_ENABLED = False       # Interrumpir respuesta con el wake word (sin AEC)
```

Si decís "JARVIS" durante la ventana de conversación, se reinicia el ciclo con un nuevo comando.

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
| **Recordatorios** | "recordame tomar agua en 10 minutos", "recordame llamar a mamá a las 3 pm" |

### Recordatorios

Podés indicar un tiempo relativo o una hora concreta:

```text
"recordame sacar la ropa en 10 minutos"
"recordame revisar el horno en media hora"
"recordame llamar a mamá a las 3 pm"
"recordame tomar el remedio a las 21:30"
```

Jarvis guarda los pendientes en `~/.local/share/jarvis/reminders.json`. Cuando
vence uno, muestra una notificación de escritorio y lo anuncia por voz. Los
recordatorios futuros se restauran automáticamente al volver a iniciar Jarvis.

### Historial de conversación

Los turnos completados se guardan en
`~/.local/share/jarvis/history.json`. Cada entrada contiene la solicitud, la
respuesta, el intent ejecutado, el resultado y la fecha. Jarvis carga este
archivo al iniciar y lo actualiza mediante reemplazo atómico para que un corte
no deje JSON incompleto.

### Pronunciación del asistente

El vocabulario de `jarvis/data/standard_phrases_rioplatense.txt` ayuda a Whisper
a reconocer órdenes como "abrí", "buscá", "revisá" y "recordame". Es una ayuda
de entrada y no modifica la respuesta.

La salida TTS usa otra capa: corrige tildes conocidas, conserva la puntuación y
convierte términos extranjeros mediante excepciones fonéticas verificadas. El
diccionario inicial incluye Google, GitHub, OpenCode y pytest. No se agregan
tildes inventadas de forma general porque podrían empeorar la pronunciación.

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
WAKE_ENGINE = "xslr"             # "openwakeword" (default) o "xslr" (entrenada)
WAKE_THRESHOLD = 0.7             # Sensibilidad (0.1-0.9); evitar falsos positivos
WAKE_CUSTOM_MODEL = None         # ONNX entrenado; None = hey_jarvis_v0.1.onnx

# Audio
AUDIO_SAMPLE_RATE = 16000
AUDIO_BLOCK_MS = 100
AUDIO_SILENCE_MS = 800           # Corte por silencio
AUDIO_MAX_UTTERANCE_S = 120.0    # Red de seguridad: dictado largo hasta 2 min
AUDIO_CALIBRATE_MS = 500         # Calibración de ruido al wake
AUDIO_CALIBRATE_FACTOR = 1.2     # umbral = ruido de fondo × factor
AUDIO_FLUSH_MS = 1000            # Descarta mic residual post-respuesta

# VAD
AUDIO_USE_SILERO_VAD = True      # Silero VAD ONNX (recomendado) / False = energy
AUDIO_SILERO_THRESHOLD = 0.5     # Umbral Silero (0.0-1.0)

# Conversación
CONVERSATION_WINDOW_S = 8.0      # Follow-up sin wake word; 0 = off
BARGE_IN_ENABLED = False         # Interrumpir respuesta con wake word (sin AEC)
BARGE_IN_WAKE_THRESHOLD = 0.85   # Umbral alto para barge-in

# TTS
TTS_ENGINE = "edge"
EDGE_VOICE = "es-MX-JorgeNeural"

# STT
WHISPER_MODEL = SPIKE / "ggml-small.bin"
WHISPER_BEAM = 1
STT_USE_TINY = False
STT_PHRASES_FILE = "jarvis/data/standard_phrases_rioplatense.txt"
STT_PROMPT = "<cargado desde STT_PHRASES_FILE>"

# LLM
LLM_PROVIDER = "local"           # "local" | "gemini" | "auto"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_S = 30.0          # cold start necesita tiempo

# Sugerencias de patrones de uso
USAGE_PATTERN_MIN_COUNT = 5      # Mínima frecuencia para sugerir un patrón

# Seguridad
AUTO_EXECUTE = False             # False = confirmar antes de ejecutar
SAFETY_GATE = "strict"           # "auto" | "strict" | "yolo" (ver sección 13)
DANGEROUS_PATTERNS = 40          # conteo real de patrones de peligro (deriva de schema)
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

Jarvis implementa 3 capas de seguridad (T-SAFE-01/02). La capa 1 y 2 son
fijas (no dependen de la config); la capa 3 la controla `SAFETY_GATE`.

### Capa 1: Golden gate (intents destructivos hablados)

Frases destructivas se reconocen ANTES de consultar el modelo, con patrones
rioplatenses exactos, y siempre piden confirmación:

- Apagar/reiniciar: "cerrá linux", "reiniciá la máquina", "apagate"
- Formatear: "formateá el disco", "formateá la memoria"
- Borrar todo: "borrá el sistema", "borrá todo", "eliminá todo en el disco",
  "borrá todos mis archivos"
- Matar procesos: "matá un proceso", "cortá un proceso"

Los intents **bloqueados por política** (`format_disk`, `wipe_system`,
`delete_all`, `kill_process`) no solo piden confirmación: Jarvis los **rechaza
hablado** con una negativa y no los ejecuta en ninguna circunstancia.
`shutdown`, `reboot` y `power_off_self` sí se ejecutan tras tu confirmación.

### Capa 2: Patrones peligrosos (40 patrones)

Todo comando que pasa por el agente se compara contra `DANGEROUS_PATTERNS`
regex que detectan efectos destructivos aunque usen binarios permitidos:

- `rm -rf /` `~/ *` `*`, `find ... -exec rm`
- `dd`/`mkfs`/`fdisk`/LVM sobre discos, `wipefs`, `blkdiscard`
- `chmod -R 777`, `chmod +s`, `chmod 000 /`
- `kill -9`, `killall` de systemd/X/audio, `systemctl stop/poweroff`
- `apt/dpkg remove` de paquetes base, `umount /`, `tar -C /`
- `git push --force`, `git reset --hard`
- `curl | sh`, `wget | sh`, escrituras a `/dev` y `/etc`
- Lectura de claves SSH / `.env`, `iptables -F`, fork bombs

Un comando que matchea **siempre** se confirma, incluso con `AUTO_EXECUTE`
activado o `SAFETY_GATE = "auto"`.

### Capa 3: Approval gate (`SAFETY_GATE`)

Controla cuándo se pide confirmación por voz para los comandos rutinarios:

- **strict** (default): pide confirmación para TODOS los comandos
- **auto**: sigue a `AUTO_EXECUTE` (False = confirmar todo; True = ejecutar
  rutinarios sin preguntar, los peligrosos de la Capa 2 siempre confirman)
- **yolo**: ejecuta rutinarios sin preguntar; los peligrosos y los destructivos
  de la Capa 1 siguen confirmando (yolo acelera lo rutinario, no desbloquea
  lo destructivo)

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
