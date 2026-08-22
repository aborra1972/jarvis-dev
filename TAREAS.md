# Plan de Trabajo — Mejoras GitHub Study (jarvis-mvp)

**Fecha**: 2026-08-22
**Fuente**: Estudio de 10+ proyectos GitHub (`docs/github-jarvis-study.md`)
**Estrategia**: Tareas cortas (max 1-2 archivos por tarea), con criterio de completitud explicito.

---

## Reglas para la IA que retome

1. **Leer este archivo primero** — marca el estado actual de cada tarea
2. **Marcar `[x]` solo cuando la tarea esta completa** (codigo escrito + tests passing o doc actualizada)
3. **Guardar en engram** despues de completar cada tarea con `mem_save`
4. **Commit despues de cada tarea completada** — nunca acumular
5. **Actualizar este archivo** — cambiar `[ ]` a `[x]` al completar
6. **Si se corta la quota**: la proxima IA lee este archivo, busca el primer `[ ]`, y empieza ahi

---

## Fase 1: Diagnostico y Verificacion (Prioridad 1-2)

### T-DIAG-01: Crear `jarvis diagnose` command
**Fuente**: NaomiProject/Naomi/diagnose.py
**Archivos**: `jarvis/src/jarvis/diagnose.py`, `jarvis/src/jarvis/cli.py`
**Que hacer**:
- Comando `jarvis diagnose` que verifica: microfono, wake word, whisper, piper, ollama, audio output
- Cada check imprime ✅ o ❌ con mensaje de que hacer si falla
- Exit code 0 si todo OK, 1 si hay fallos criticos

**Criterio de completitud**:
- [ ] `jarvis diagnose` corre sin errores
- [ ] Muestra ✅/❌ para cada componente
- [ ] Exit code correcto (0 = todo OK, 1 = fallos)
- [ ] README.md actualizado con seccion de diagnostico
- [ ] Tests basicos (mock de cada check)

**Estado**: `[ ]` Pendiente

### T-DIAG-02: Agregar `diagnose` al CLI
**Archivos**: `jarvis/src/jarvis/cli.py`
**Que hacer**:
- Agregar subcomando `diagnose` al entry point
- Importar y ejecutar `diagnose.py`

**Criterio de completitud**:
- [ ] `python -m jarvis diagnose` funciona
- [ ] `--help` muestra el subcomando

**Estado**: `[ ]` Pendiente

---

## Fase 2: VAD y Audio (Prioridad 3-6)

### T-VAD-01: Agregar Silero VAD como dependencia
**Archivos**: `pyproject.toml` o `requirements.txt`
**Que hacer**:
- Agregar `torch` y `silero-vad` a las dependencias
- Verificar que el modelo se descarga automaticamente

**Criterio de completitud**:
- [ ] `pip install -e .` instala silero-vad
- [ ] `import silero_vad` funciona

**Estado**: `[ ]` Pendiente

### T-VAD-02: Implementar Silero VAD en `capture.py`
**Archivos**: `jarvis/src/jarvis/audio/capture.py`
**Que hacer**:
- Reemplazar energy threshold con Silero VAD
- Configurar: threshold=0.5, min_speech_ms=250, min_silence_ms=500
- Fallback a energy VAD si Silero no esta disponible

**Criterio de completitud**:
- [ ] Silero VAD detecta voz vs silencio
- [ ] Fallback a energy VAD funciona
- [ ] Tests unitarios con audio simulado

**Estado**: `[ ]` Pendiente

### T-CALIB-01: Calibracion de ruido ambiente al wake
**Archivos**: `jarvis/src/jarvis/audio/capture.py`
**Que hacer**:
- Al detectar wake word, grabar 500ms de fondo
- Calcular RMS promedio como noise floor
- Ajustar umbral dinamicamente (noise_floor * 1.2)

**Criterio de completitud**:
- [ ] Calibracion corre al detectar wake
- [ ] Umbral se ajusta dinamicamente
- [ ] Config option `AUDIO_CALIBRATE_MS`

**Estado**: `[ ]` Pendiente

### T-FLUSH-01: Flush de buffer stale post-playback
**Archivos**: `jarvis/src/jarvis/audio/capture.py` o `playback.py`
**Que hacer**:
- Despues de TTS playback, leer y descartar 1s de audio del mic
- Evita que el audio del speaker trigger wake word falso

**Criterio de completitud**:
- [ ] Flush corre despues de cada playback
- [ ] No hay falsos positivos post-playback
- [ ] Config option `AUDIO_FLUSH_MS` (default 1000)

**Estado**: `[ ]` Pendiente

---

## Fase 3: Seguridad (Prioridad 7-8)

### T-SAFE-01: Agregar 3 capas de seguridad al golden gate
**Archivos**: `jarvis/src/jarvis/interpreter/golden.py`
**Que hacer**:
- Capa 1: Hardline blocklist (siempre bloqueado) — ~10 patrones
- Capa 2: Dangerous patterns (~40 patrones) con warning
- Capa 3: Approval gate (auto/strict/yolo)

**Criterio de completitud**:
- [ ] Hardline blocklist bloquea comandos catastroficos
- [ ] Dangerous patterns detecta ~40 patrones
- [ ] Approval gate configurable
- [ ] Tests para cada capa

**Estado**: `[ ]` Pendiente

### T-SAFE-02: Agregar config de seguridad
**Archivos**: `jarvis/src/jarvis/config.py`
**Que hacer**:
- `SAFETY_GATE = "strict"` (auto/strict/yolo)
- `DANGEROUS_PATTERNS = 40`

**Criterio de completitud**:
- [ ] Config options existen
- [ ] Documentadas en README y MANUAL_USUARIO

**Estado**: `[ ]` Pendiente

---

## Fase 4: NLU Classifier (Prioridad 9-10)

### T-NLU-01: Implementar TF-IDF + LogReg classifier
**Archivos**: `jarvis/src/jarvis/interpreter/nlu_classifier.py`
**Que hacer**:
- Clase `IntentClassifier` con vectorizer + classifier
- Entrenar con ejemplos de comandos rioplatenses
- Cache con joblib en `~/.local/share/jarvis/nlu`

**Criterio de completitud**:
- [ ] Classifier entrena con ejemplos
- [ ] Predice intents con confianza
- [ ] Cache funciona (joblib)
- [ ] Tests unitarios

**Estado**: `[ ]` Pendiente

### T-NLU-02: Integrar NLU en el pipeline
**Archivos**: `jarvis/src/jarvis/interpreter/golden.py`, `jarvis/src/jarvis/orchestrator/loop.py`
**Que hacer**:
- NLU corre antes del LLM para intents no destructivos
- Si confianza >= 0.65, usa NLU (rapido)
- Si confianza < 0.65, fallback a LLM

**Criterio de completitud**:
- [ ] NLU se integra en el pipeline
- [ ] Fallback a LLM funciona
- [ ] Config option `NLU_ENABLED` y `NLU_CONFIDENCE`

**Estado**: `[ ]` Pendiente

---

## Fase 5: Multi-turn y Dictation (Prioridad 11-13)

### T-MULTI-01: Agregar estado follow-up al FSM
**Archivos**: `jarvis/src/jarvis/orchestrator/state.py`, `jarvis/src/jarvis/orchestrator/loop.py`
**Que hacer**:
- Nuevo estado `followup` despues de `speaking`
- Timeout configurable (10s por defecto)
- Si hay input durante followup, procesar directamente
- Si wake word durante followup, reiniciar ciclo

**Criterio de completitud**:
- [ ] Estado follow-up existe en FSM
- [ ] Timeout funciona (10s)
- [ ] Input durante followup se procesa
- [ ] Wake word reinicia ciclo
- [ ] Config option `FOLLOWUP_TIMEOUT_S`

**Estado**: `[ ]` Pendiente

### T-DICT-01: Implementar `jarvis dictation` mode
**Archivos**: `jarvis/src/jarvis/cli.py`, `jarvis/src/jarvis/dictation.py`
**Que hacer**:
- Modo dictado: escucha continua, transcribe, escribe texto
- Deteccion de pausas (800ms) como fin de frase
- Salida con Ctrl+C o "para dictado"
- Usar wtype/xdotool para escribir en foco actual

**Criterio de completitud**:
- [ ] `jarvis dictation` funciona
- [ ] Transcribe continuamente
- [ ] Sale con Ctrl+C o "para dictado"
- [ ] Escribe texto en foco actual

**Estado**: `[ ]` Pendiente

---

## Fase 6: Rapidfuzz y Recordatorios (Prioridad 14-16)

### T-FUZZY-01: Reemplazar difflib con rapidfuzz
**Archivos**: `jarvis/src/jarvis/interpreter/golden.py`, `requirements.txt`
**Que hacer**:
- Agregar `rapidfuzz` a dependencias
- Reemplazar `difflib.SequenceMatcher` con `rapidfuzz.fuzz.ratio`
- Fallback a difflib si rapidfuzz no esta disponible

**Criterio de completitud**:
- [ ] `rapidfuzz` en requirements.txt
- [ ] Import con fallback funciona
- [ ] Fuzzy matching usa rapidfuzz

**Estado**: `[ ]` Pendiente

### T-REMIND-01: Modulo de recordatorios
**Archivos**: `jarvis/src/jarvis/actions/reminders.py`
**Que hacer**:
- Parseo de tiempo natural ("en 10 minutos", "a las 3pm")
- Timer en background
- notify-send + TTS cuando vence
- Persistencia en `~/.local/share/jarvis/reminders.json`

**Criterio de completitud**:
- [ ] Parseo de tiempo funciona
- [ ] Timer dispara notificacion
- [ ] notify-send + TTS al vencer
- [ ] Persistencia funciona

**Estado**: `[ ]` Pendiente

---

## Fase 7: Standard Phrases y Persistencia (Prioridad 17-18)

### T-PHRASES-01: Standard phrases rioplatenses
**Archivos**: `jarvis/src/jarvis/config.py`, `jarvis/data/standard_phrases_rioplatense.txt`
**Que hacer**:
- Crear archivo con palabras que el usuario realmente dice
- Pasar como `--prompt` a whisper-cli para sesgar STT
- Incluir: "abri", "cerre", "busca", "crea", "manda", etc.

**Criterio de completitud**:
- [ ] Archivo `standard_phrases_rioplatense.txt` creado
- [ ] Whisper usa prompt con frases
- [ ] Config option `STT_PROMPT`

**Estado**: `[ ]` Pendiente

### T-HIST-01: Persistencia de conversacion atomica
**Archivos**: `jarvis/src/jarvis/orchestrator/session.py`
**Que hacer**:
- Historial en `~/.local/share/jarvis/history.json`
- Escritura atomica con temp+rename
- Leer al iniciar, guardar al cambiar
- No se corrompe si se corta

**Criterio de completitud**:
- [ ] Historial se guarda atomicamente
- [ ] Se carga al iniciar
- [ ] No se corrompe con cortes

**Estado**: `[ ]` Pendiente

---

## Fase 8: Agentes IA por voz expandidos (Prioridad 19)

### T-AGENT-01: Expandir comandos de agente por voz
**Archivos**: `jarvis/src/jarvis/actions/opencode.py`, `jarvis/src/jarvis/interpreter/schema.py`
**Que hacer**:
- Agregar intents: `review_pr`, `fix_warnings`, `create_artifact`
- Cada intent abre repo en OpenCode con comando especifico
- Notificacion cuando termine

**Criterio de completitud**:
- [ ] Nuevos intents en schema
- [ ] Executors implementados
- [ ] Notificacion al terminar
- [ ] Tests para cada intent

**Estado**: `[ ]` Pendiente

---

## Resumen de progreso

| Fase | Tareas | Completadas | Pendientes |
|------|--------|-------------|------------|
| 1. Diagnostico | 2 | 0 | 2 |
| 2. VAD y Audio | 4 | 0 | 4 |
| 3. Seguridad | 2 | 0 | 2 |
| 4. NLU | 2 | 0 | 2 |
| 5. Multi-turn | 2 | 0 | 2 |
| 6. Rapidfuzz | 2 | 0 | 2 |
| 7. Phrases/Hist | 2 | 0 | 2 |
| 8. Agentes IA | 1 | 0 | 1 |
| **Total** | **17** | **0** | **17** |

---

## Proxima tarea a ejecutar

**T-DIAG-01**: Crear `jarvis diagnose` command

Es la primera tarea pendiente y la mas facil de verificar.
Una vez completa, seguir con T-DIAG-02, luego Fase 2 (VAD), etc.

---

*Ultima actualizacion: 2026-08-22*
