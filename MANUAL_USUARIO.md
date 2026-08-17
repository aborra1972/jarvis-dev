# J.A.R.V.I.S. — Manual de Usuario Completo

## Índice

1. [Qué es Jarvis](#1-qué-es-jarvis)
2. [Requisitos del sistema](#2-requisitos-del-sistema)
3. [Instalación](#3-instalación)
4. [Primer uso](#4-primer-uso)
5. [Panel de control (GUI)](#5-panel-de-control-gui)
6. [Uso por voz](#6-uso-por-voz)
7. [Comandos disponibles](#7-comandos-disponibles)
8. [Configuración](#8-configuración)
9. [Wake word personalizado](#9-wake-word-personalizado)
10. [Solución de problemas](#10-solución-de-problemas)
11. [Comandos de terminal](#11-comandos-de-terminal)
12. [Arquitectura](#12-arquitectura)

---

## 1. Qué es Jarvis

**J.A.R.V.I.S.** es un asistente de voz local para Linux, inspirado en el JARVIS de las películas de Marvel. Funciona 100% en tu computadora — sin internet, sin nube, sin suscripciones.

**Características principales:**
- 🎤 Reconocimiento de voz local con Whisper
- 🗣️ Respuestas por voz con Edge TTS (neural)
- 🧠 Integración con OpenCode para desarrollo
- 🔒 Privacidad total — todo queda en tu máquina
- 🎯 Wake word personalizado "jarvis" con tu pronunciación

**Stack tecnológico:**
- **STT**: Whisper.cpp (tiny/small/medium) — tiny para máxima velocidad
- **TTS**: Edge TTS (es-MX-JorgeNeural) + Piper (offline fallback)
- **LLM**: Ollama local (qwen2.5:3b) + Gemini cloud con fallback automático
- **Wake Word**: wav2vec2-XLSR + LogisticRegression (ONNX)
- **Acciones**: OpenCode serve + Python executors
- **GUI**: GTK3 (panel de control con estado en tiempo real)

---

## 2. Requisitos del sistema

### Mínimos
- **SO**: Linux (probado en Linux Mint 22.3)
- **RAM**: 4GB mínimo, 8GB recomendado
- **Disco**: 2GB para modelos y dependencias
- **Micrófono**: Cualquier micrófono USB o integrado
- **Audio**: ALSA o PipeWire funcionando

### Dependencias del sistema
```bash
# Audio
sudo apt install alsa-utils pulseaudio

# Python 3.12+
sudo apt install python3.12 python3.12-venv

# Git
sudo apt install git
```

### Hardware recomendado
- Micrófono con cancelación de ruido
- Altavoces o auriculares para respuesta por voz
- Procesador con al menos 4 cores (para inferencia local)

---

## 3. Instalación

### Desde cero

```bash
# 1. Clonar el repositorio
git clone https://github.com/aborra1972/jarvis-dev.git
cd jarvis-dev

# 2. Crear entorno virtual
python3.12 -m venv jarvis/.venv
source jarvis/.venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Verificar instalación
python -m jarvis --help
```

### Verificar que funciona

```bash
# Test de importación
python -c "import jarvis; print(jarvis.__version__)"

# Test de audio
python -c "import sounddevice; print(sounddevice.query_devices())"
```

---

## 4. Primer uso

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
# Crear alias (agregar a ~/.bashrc)
echo 'alias jarvis="cd /home/ale/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m jarvis"' >> ~/.bashrc
source ~/.bashrc

# Ahora podés usar:
jarvis start
jarvis off
jarvis on
```

---

## 5. Panel de control (GUI)

El panel de control es una ventana flotante que aparece en la esquina superior derecha de la pantalla.

### Elementos del panel

```
┌─────────────────────────────┐
│  J.A.R.V.I.S.         v1.0 │
│  Asistente de Voz Local     │
├─────────────────────────────┤
│  ● ACTIVO                   │
│  Escuchando 'JARVIS'...     │
├─────────────────────────────┤
│                             │
│     ⏻ ENCENDER / APAGAR     │
│                             │
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

- **Baja (0.1-0.3)**: Solo detecta con pronunciación muy clara y silencio
- **Media (0.4-0.6)**: Balance entre sensibilidad y falsos positivos (recomendado)
- **Alta (0.7-0.9)**: Detecta fácil pero puede activarse con ruido

### Indicador de estado en tiempo real

El panel muestra qué está haciendo Jarvis:

- **● ESCUCHANDO**: Esperando wake word "JARVIS"
- **● ESCUCHANDO: [texto]**: Grabando tu comando
- **● PENSANDO**: Procesando tu comando (LLM)
- **● EJECUTANDO: [comando]**: Ejecutando la acción
- **● CONFIRMANDO**: Esperando confirmación para acción destructiva
- **● HABLANDO**: Jarvis está hablando
- **● APAGADO**: Modo off — diga "jarvis on"

---

## 6. Uso por voz

### Flujo básico

1. **Activar**: Decí "JARVIS" con tu pronunciación natural
2. **Comando**: Decí lo que necesitás (ej: "abrí la terminal")
3. **Respuesta**: Jarvis confirma y ejecuta
4. **Repetir**: Para otro comando, volvé a decir "JARVIS"

### Pronunciación

- **"jarvis"** se detecta con la jota argentina (/x/)
- No es necesario decir "hey" antes
- Funciona a volumen normal de conversación
- Si hay ruido, acercate al micrófono

### Ejemplos de uso

```
Tú: "JARVIS"
Jarvis: [sonido de confirmación]
Tú: "abrí firefox"
Jarvis: "Abriendo Firefox, señor"
[Se abre Firefox]

Tú: "JARVIS"
Tú: "creá una carpeta llamada proyecto"
Jarvis: "Carpeta 'proyecto' creada, señor"
```

---

## 7. Comandos disponibles

Ver la referencia completa en `docs/comandos_jarvis.md`.

### Resumen rápido

| Categoría | Comandos principales |
|-----------|---------------------|
| **Sistema** | "abrí la terminal", "abrí firefox", "cerrá firefox" |
| **Archivos** | "creá una carpeta", "borrá el archivo" |
| **Web** | "buscá [término]", "abri [url]" |
| **Desarrollo** | "mostrá el estado", "creá un commit" |
| **Asistente** | "¿Qué podés hacer?", "apagá" |

### Comandos de confirmación

Algunos comandos destructivos piden confirmación:
- "borrá el archivo X" → Jarvis pregunta "¿Confirmo?"
- Respondé **"sí"** o **"no"** para confirmar o cancelar

---

## 8. Configuración

### Archivo de configuración

`jarvis/src/jarvis/config.py` contiene todas las opciones. Podés sobreescribirlas con `.env` en la raíz del repo:

```python
# Wake word
WAKE_ENGINE = "xslr"           # "xslr" (custom) u "openwakeword"
WAKE_THRESHOLD = 0.5           # Sensibilidad (0.1-0.9)
WAKE_XLSR_MODEL = SPIKE / "models" / "jarvis_wake.onnx"

# Audio
AUDIO_SAMPLE_RATE = 16000      # Frecuencia de muestreo
AUDIO_BLOCK_MS = 100           # Tamaño de bloque
AUDIO_SILENCE_MS = 800         # Tiempo de silencio para corte

# Voz (TTS)
TTS_ENGINE = "edge"            # "edge" (neural) o "piper" (offline)
EDGE_VOICE = "es-MX-JorgeNeural"

# STT (Whisper)
WHISPER_MODEL = SPIKE / "ggml-small.bin"
WHISPER_BEAM = 1               # Beam size (1=rápido, 5=preciso)
STT_USE_TINY = False           # True: usa ggml-tiny.bin (~2-5x más rápido)

# LLM (opciones de proveedor)
LLM_PROVIDER = "local"         # "local" | "gemini" | "auto"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_S = 15.0        # cold start necesita tiempo
```

### Cambiar la sensibilidad

**Desde el panel**: Usá el slider

**Desde terminal**:
```bash
# Editar config.py
WAKE_THRESHOLD = 0.3  # más sensible
# o
WAKE_THRESHOLD = 0.7  # menos sensible
```

### Cambiar la voz

```python
# En config.py
EDGE_VOICE = "es-MX-DaliaNeural"   # femenina
EDGE_VOICE = "es-MX-JorgeNeural"   # masculina (default)
EDGE_VOICE = "es-AR-TomasNeural"   # argentino
```

### Usar TTS offline (Piper)

```python
TTS_ENGINE = "piper"
```

---

## 9. Wake word personalizado

### Cómo funciona

Jarvis usa un modelo de inteligencia artificial para detectar la palabra "jarvis" con tu pronunciación argentina. El modelo fue entrenado con tu voz.

### Re-entrenar el wake word

Si Jarvis no te detecta bien, podés re-entrenar con más muestras:

```bash
# 1. Grabar más positivos (decí "jarvis" ~30 veces)
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/grabar_wake.py pos -n 30

# 2. Grabar más negativos (otras frases ~20 veces)
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/grabar_wake.py neg -n 20

# 3. Re-extraer embeddings
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/extraer_xlsr.py

# 4. Re-entrenar y exportar
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/entrenar_clasificador.py --export-onnx

# 5. Copiar modelo nuevo
cp /tmp/opencode/train/modelo_wake/clasificador.onnx spike/models/jarvis_wake.onnx
```

### Métricas objetivo

- **Recall ≥ 90%**: Detecta "jarvis" el90% de las veces
- **FP ≤ 10%**: Se activa incorrectamente menos del 10%

---

## 10. Solución de problemas

### Jarvis no detecta "jarvis"

1. **Bajá la sensibilidad**: Slider a 0.3-0.4
2. **Grabá más muestras**: Sigue el proceso de re-entrenamiento
3. **Verificá el micrófono**: `arecord -l` debe mostrar tu dispositivo
4. **Probá con "hey jarvis"**: El modelo preentrenado funciona mejor con "hey"

### Jarvis se activa solo

1. **Subí la sensibilidad**: Slider a 0.6-0.7
2. **Verificá el ruido**: Cerrá ventanas con audio
3. **Re-entrená con negativos**: Grabá más muestras de ruido

### No hay audio

1. **Verificá dispositivos**: `arecord -l` y `aplay -l`
2. **Reiniciá audio**: `pulseaudio -k && pulseaudio --start`
3. **Verificá permisos**: `usermod -aG audio $USER` (requiere re-login)

### Jarvis no ejecuta comandos

1. **Verificá proyecto activo**: Jarvis necesita un proyecto abierto
2. **Revisá logs**: Usá el botón 📋 del panel
3. **Reiniciá**: Apagá y encendé con el botón on/off

### Errores de Python

```bash
# Reinstalar dependencias
source jarvis/.venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verificar imports
python -c "import jarvis; print('OK')"
```

---

## 11. Comandos de terminal

### Lifecycle

```bash
jarvis start    # Iniciar Jarvis con GUI
jarvis off      # Apagar (mic liberado, no escucha)
jarvis on       # Reanudar escucha
jarvis clean    # Limpiar logs y archivos temporales
jarvis logs     # Ver logs (próximamente)
```

### Signals (desde otra terminal)

```bash
# Encontrar PID de Jarvis
cat ~/.local/state/jarvis/jarvis.pid

# Apagar
kill -SIGUSR1 $(cat ~/.local/state/jarvis/jarvis.pid)

# Encender
kill -SIGUSR2 $(cat ~/.local/state/jarvis/jarvis.pid)
```

---

## 12. Arquitectura

### Diagrama de componentes

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Micrófono  │────▶│  Wake Word   │────▶│  Whisper STT│
│ (sounddevice)│     │ (XLSR+ONNX) │     │ (whisper-cli)│
└─────────────┘     └──────────────┘     └─────────────┘
                                                 │
                                                 ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Altavoces  │◀────│   Edge TTS   │◀────│  Interpreter │
│  (paplay)   │     │  (Microsoft) │     │   (OpenCode) │
└─────────────┘     └──────────────┘     └─────────────┘
                                                 │
                                                 ▼
                                        ┌──────────────┐
                                        │   Executor   │
                                        │ (opencode)   │
                                        └──────────────┘
```

### Flujo de datos

1. **Captura**: sounddevice graba audio a 16kHz mono
2. **Wake Word**: wav2vec2-XLSR detecta "jarvis" (354ms)
3. **STT**: Whisper transcribe audio a texto
4. **Interpretación**: OpenCode interpreta la intención
5. **Ejecución**: Executor realiza la acción
6. **Respuesta**: Edge TTS sintetiza voz de respuesta
7. **Reproducción**: paplay/gst reproduce el audio

### Modelos utilizados

| Componente | Modelo | Tamaño | Latencia |
|------------|--------|--------|----------|
| Wake Word | wav2vec2-large-xlsr-53 | 1.2GB | ~350ms |
| Classifier | LogisticRegression (ONNX) | 21KB | <1ms |
| STT | whisper small | 487MB | ~4s |
| TTS | Edge TTS (neural) | cloud | ~2s |

---

## Soporte

- **Repositorio**: github.com/aborra1972/jarvis-dev
- **Issues**: Abrí un issue para bugs o sugerencias
- **Docs**: `jarvis/docs/` en el repositorio

---

*J.A.R.V.I.S. — Just A Rather Very Intelligent System*
*Versión 1.0 — Agosto 2026*
