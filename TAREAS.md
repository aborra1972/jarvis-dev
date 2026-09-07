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

### T-DIAG-01: Crear `jarvis diagnose` command [COMPLETADA]
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

**Estado**: `[x]` Completada

### T-DIAG-02: Agregar `diagnose` al CLI
**Archivos**: `jarvis/src/jarvis/cli.py`
**Que hacer**:
- Agregar subcomando `diagnose` al entry point
- Importar y ejecutar `diagnose.py`

**Criterio de completitud**:
- [ ] `python -m jarvis diagnose` funciona
- [ ] `--help` muestra el subcomando

**Estado**: `[x]` Completada

---

## Fase 2: VAD y Audio (Prioridad 3-6)

### T-VAD-01: Agregar Silero VAD como dependencia
**Archivos**: `pyproject.toml` o `requirements.txt`
**Que hacer**:
- Agregar `torch` y `silero-vad` a las dependencias
- Verificar que el modelo se descarga automaticamente

**Criterio de completitud**:
- [x] `pip install -e .` instala silero-vad
- [x] `import silero_vad` funciona

**Estado**: `[x]` Completada

### T-VAD-02: Implementar Silero VAD en `capture.py`
**Archivos**: `jarvis/src/jarvis/audio/capture.py`
**Que hacer**:
- Reemplazar energy threshold con Silero VAD
- Configurar: threshold=0.5, min_speech_ms=250, min_silence_ms=500
- Fallback a energy VAD si Silero no esta disponible

**Criterio de completitud**:
- [x] Silero VAD detecta voz vs silencio
- [x] Fallback a energy VAD funciona
- [x] Tests unitarios con audio simulado

**Estado**: `[x]` Completada

### T-CALIB-01: Calibracion de ruido ambiente al wake
**Archivos**: `jarvis/src/jarvis/audio/capture.py`
**Que hacer**:
- Al detectar wake word, grabar 500ms de fondo
- Calcular RMS promedio como noise floor
- Ajustar umbral dinamicamente (noise_floor * 1.2)

**Criterio de completitud**:
- [x] Calibracion corre al detectar wake
- [x] Umbral se ajusta dinamicamente
- [x] Config option `AUDIO_CALIBRATE_MS`

**Estado**: `[x]` Completada

### T-FLUSH-01: Flush de buffer stale post-playback
**Archivos**: `jarvis/src/jarvis/audio/capture.py` o `playback.py`
**Que hacer**:
- Despues de TTS playback, leer y descartar 1s de audio del mic
- Evita que el audio del speaker trigger wake word falso

**Criterio de completitud**:
- [x] Flush corre despues de cada playback
- [x] No hay falsos positivos post-playback
- [x] Config option `AUDIO_FLUSH_MS` (default 1000)

**Estado**: `[x]` Completada

---

## Fase 3: Seguridad (Prioridad 7-8)

### T-SAFE-01: Agregar 3 capas de seguridad al golden gate
**Archivos**: `jarvis/src/jarvis/interpreter/golden.py`, `jarvis/src/jarvis/actions/base.py`
**Que hacer**:
- Capa 1: Hardline blocklist (siempre bloqueado) — ~10 patrones
- Capa 2: Dangerous patterns (~40 patrones) con warning
- Capa 3: Approval gate (auto/strict/yolo)

**Avance 2026-09-05 (completa)**:
- [x] Intents destructivos (`format_disk`, `wipe_system`, `delete_all`, `kill_process`) registrados como `blocked_destructive` en `build_registry()` — rechazan con negativa hablada
- [x] `format_disk`, `wipe_system` en `DOMAIN_INTENTS["system"]`
- [x] Tests de gating destructivo (`tests/unit/test_schema.py`)
- [x] Hardline blocklist completo del golden gate: los 7 intents destructivos (shutdown, reboot, power_off_self + format_disk, wipe_system, delete_all, kill_process) salen por patrones rioplatenses full-anchored con `confirm_required=True`, sin consultar al LLM. Los 4 sin operador real salen con `blocked=True` (política: `POLICY_BLOCKED_INTENTS` en golden.py) → el handler `blocked_destructive` los rechaza hablado
- [x] Dangerous patterns: `_DANGEROUS_COMMAND_PATTERNS` expandido a 40 patrones en schema.py (catastróficos rm, dd/mkfs/fdisk/LVM, chmod/chown abusivos, kill -9/killall/systemctl, apt/dpkg base, escrituras a /dev//etc, umount/tar, git push -f, curl|sh, secretos SSH/.env, iptables -F, fork bomb) + `dangerous_pattern_count()` derivado en vivo
- [x] Approval gate configurable (`SAFETY_GATE` auto/strict/yolo) con política real: yolo nunca desbloquea destructivos del gate; auto confirma siempre comandos peligrosos
- [x] Tests por capa + matriz 57 peligrosos / 37 seguros + M6 extendido a los 7 destructivos — suite completa 791 passed, 0 failed

**Estado**: `[x]` Completada

### T-SAFE-02: Agregar config de seguridad
**Archivos**: `jarvis/src/jarvis/config.py`
**Que hacer**:
- `AUTO_EXECUTE = False` ✅ (ya existe: False = confirmar antes de ejecutar)
- `SAFETY_GATE = "strict"` (auto/strict/yolo) — completado
- `DANGEROUS_PATTERNS = 40` — completado

**Criterio de completitud**:
- [x] `AUTO_EXECUTE` existe y está documentado (README + MANUAL)
- [x] Config options `SAFETY_GATE` y `DANGEROUS_PATTERNS` existen — `SAFETY_GATE = "strict"` (auto/strict/yolo) y `DANGEROUS_PATTERNS = dangerous_pattern_count()` (derivado en vivo de `schema._DANGEROUS_COMMAND_PATTERNS`, hoy 40)

**Estado**: `[x]` Completada

---

## Fase 4: NLU Classifier (Prioridad 9-10)

### T-NLU-01: Implementar TF-IDF + LogReg classifier
**Archivos**: `jarvis/src/jarvis/interpreter/nlu.py`
**Que hacer**:
- Clase/clasificador con vectorizer TF-IDF + LogisticRegression
- Entrenado con ejemplos de comandos rioplatenses embebidos en el módulo
- Devuelve `Suggestion(intent, confidence, spoken)` o `None`

**Criterio de completitud**:
- [x] Clasifica comandos con confianza (ej: "abrir firefox" → open_app)
- [x] Devuelve `None` para frases fuera de dominio
- [x] Nunca lanza (guardado con try/except, sklearn lazy)
- [x] Tests unitarios (`tests/unit/test_nlu.py`)

**Estado**: `[x]` Completada

### T-NLU-02: Integrar NLU en el pipeline
**Archivos**: `jarvis/src/jarvis/interpreter/interpreter.py`, `jarvis/src/jarvis/orchestrator/loop.py`
**Que hacer**:
- Cuando el intérprete no entiende, NLU ofrece una sugerencia hablada
- **No ejecuta nada** — solo un hint de qué intención probablemente quisiste decir
- Nunca interfiere con el routing LLM normal

**Criterio de completitud**:
- [x] `interpreter.py` consulta `nlu.classify()` cuando no hay intent
- [x] La sugerencia se habla, nunca se ejecuta
- [x] Protegido contra fallos (nunca rompe el loop)
- [x] Tests de integración (`tests/unit/test_loop.py`)

**Estado**: `[x]` Completada

---

## Fase 5: Multi-turn y Dictation (Prioridad 11-13)

### T-MULTI-01: Modo conversación (follow-up sin wake word)
**Archivos**: `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/src/jarvis/config.py`
**Que hacer**:
- Tras un comando exitoso, quedarse escuchando `CONVERSATION_WINDOW_S` (8s) sin wake word
- 0 = desactivado (siempre requiere "jarvis")
- La ventana se renueva tras cada comando exitoso

**Criterio de completitud**:
- [x] `CONVERSATION_WINDOW_S = 8.0` en config
- [x] Loop arma la ventana tras comando exitoso
- [x] Vuelve a requerir wake word si no hay input en la ventana
- [x] Config option documentada en README y MANUAL
- [x] Tests (`tests/unit/test_loop.py`)

**Estado**: `[x]` Completada — diseño adaptado: ventana temporal en loop.py en vez de estado FSM

### T-DICT-01: Implementar `jarvis dictation` mode
**Archivos**: `jarvis/src/jarvis/interpreter/dictation.py`, `jarvis/src/jarvis/cli.py`
**Que hacer**:
- Modo dictado: escucha continua, transcribe, escribe texto
- Deteccion de pausas (800ms) como fin de frase
- Salida con Ctrl+C o "para dictado"
- Red de seguridad de 120s (`AUDIO_MAX_UTTERANCE_S`) para dictado largo

**Criterio de completitud**:
- [x] `jarvis dictation` funciona
- [x] Transcribe continuamente
- [x] Sale con Ctrl+C o "para dictado"
- [x] Escribe texto en foco actual

**Estado**: `[x]` Completada

---

## Fase 6: Rapidfuzz y Recordatorios (Prioridad 14-16)

### T-FUZZY-01: Reemplazar difflib con rapidfuzz
**Archivos**: `jarvis/src/jarvis/interpreter/schema.py`, `jarvis/src/jarvis/interpreter/interpreter.py`, `jarvis/pyproject.toml`
**Que hacer**:
- Agregar `rapidfuzz` a `[project.dependencies]` en `pyproject.toml`
- Reemplazar `difflib.get_close_matches` con `rapidfuzz.process.extractOne` (scorer `fuzz.ratio`, cutoff 60/100) en `fuzzy_correct_entities`
- Fallback a difflib si rapidfuzz no esta disponible (import con fallback)
- Eliminar el import muerto `import difflib` en `interpreter.py`

**Criterio de completitud**:
- [x] `rapidfuzz` en `pyproject.toml` (`[project.dependencies]`)
- [x] Import con fallback funciona
- [x] Fuzzy matching usa rapidfuzz

**Estado**: `[x]` Completada

### T-REMIND-01: Modulo de recordatorios
**Archivos**: `jarvis/src/jarvis/actions/reminders.py`
**Que hacer**:
- Parseo de tiempo natural ("en 10 minutos", "a las 3pm")
- Timer en background
- notify-send + TTS cuando vence
- Persistencia en `~/.local/share/jarvis/reminders.json`

**Criterio de completitud**:
- [x] Parseo de tiempo funciona
- [x] Timer dispara notificacion
- [x] notify-send + TTS al vencer
- [x] Persistencia funciona

**Estado**: `[x]` Completada

---

## Fase 7: Standard Phrases y Persistencia (Prioridad 17-18)

### T-PHRASES-01: Standard phrases rioplatenses
**Archivos**: `jarvis/src/jarvis/config.py`, `jarvis/data/standard_phrases_rioplatense.txt`, capa TTS
**Que hacer**:
- Crear archivo con palabras que el usuario realmente dice
- Pasar como `--prompt` a whisper-cli para sesgar STT
- Incluir: "abri", "cerre", "busca", "crea", "manda", etc.
- Agregar una normalizacion TTS separada que prepare el texto hablado en castellano

**Reglas solicitadas para TTS**:
1. Usar siempre tildes ortograficas estrictas, incluso en mayusculas.
2. Usar comas y puntos para marcar pausas naturales de respiracion y enfasis.
3. Escribir foneticamente en castellano las palabras ambiguas o extranjeras cuando sea necesario (por ejemplo, "Gugel" en vez de "Google").
4. Forzar la silaba tonica solo mediante excepciones foneticas verificadas; no introducir tildes invalidas globalmente.

**Separacion tecnica**: el archivo de frases sesga la entrada STT de Whisper. Las reglas anteriores transforman exclusivamente la salida enviada al sintetizador TTS.

**Criterio de completitud**:
- [x] Archivo `standard_phrases_rioplatense.txt` creado
- [x] Whisper usa prompt con frases
- [x] Config option `STT_PROMPT`
- [x] Normalizador TTS cubierto por pruebas de tildes, puntuacion y terminos extranjeros

**Estado**: `[x]` Completada

### T-HIST-01: Persistencia de conversacion atomica
**Archivos**: `jarvis/src/jarvis/orchestrator/session.py`
**Que hacer**:
- Historial en `~/.local/share/jarvis/history.json`
- Escritura atomica con temp+rename
- Leer al iniciar, guardar al cambiar
- No se corrompe si se corta

**Criterio de completitud**:
- [x] Historial se guarda atomicamente
- [x] Se carga al iniciar
- [x] No se corrompe con cortes

**Estado**: `[x]` Completada

---

## Fase 8: Agentes IA por voz expandidos (Prioridad 19)

### T-AGENT-01: Expandir comandos de agente por voz
**Archivos**: `jarvis/src/jarvis/actions/opencode.py`, `jarvis/src/jarvis/interpreter/schema.py`
**Que hacer**:
- Agregar intents: `review_pr`, `fix_warnings`, `create_artifact`
- Cada intent abre repo en OpenCode con comando especifico
- Notificacion cuando termine

**Criterio de completitud**:
- [x] Nuevos intents en schema
- [x] Executors implementados
- [x] Notificacion al terminar (respuesta hablada final del agente)
- [x] Tests para cada intent

**Estado**: `[x]` Completada

---

## Resumen de progreso

| Fase | Tareas | Completadas | Pendientes |
|------|--------|-------------|------------|
| 1. Diagnostico | 2 | 2 | 0 |
| 2. VAD y Audio | 4 | 4 | 0 |
| 3. Seguridad | 2 | 2 | 0 |
| 4. NLU | 2 | 2 | 0 |
| 5. Multi-turn | 2 | 2 | 0 |
| 6. Rapidfuzz/Recordatorios | 2 | 2 | 0 |
| 7. Phrases/Hist | 2 | 2 | 0 |
| 8. Agentes IA | 1 | 1 | 0 |
| **Total** | **17** | **17** | **0** |

---

## Estado actual y próxima tarea

El roadmap original de 17 tareas está completo. Además, las tres voces de producción
seleccionadas en `jarvis/voice-samples/index.html` fueron restauradas y documentadas:
Jarvis (`es-NI-FedericoNeural`), Friday (`es-PE-CamilaNeural`) y Karen
(`es-GT-MartaNeural`), con rate y pitch neutrales.

La primera slice de seguridad del SDD `jarvis-persistent-conversation` está archivada
y verificada. La próxima tarea pendiente es el SDD
`jarvis-active-conversation-goodbye`, actualmente en fase de planificación; contempla
futuros PRs encadenados para (1) control determinista de goodbye, (2) época de
conversación activa y barrera playback-micrófono, y (3) cierre, invalidación de
confirmaciones y regresiones de ciclo de vida. Esta planificación no autoriza aún
implementar la slice.

## Pendientes retomados el 2026-09-06

1. Validar manualmente el flujo completo de microfono y GUI con Jarvis, Friday y Karen.
2. Tras validar Jarvis Control, escanear cada proyecto de Windows con su propio indice CodeGraph.

---

*Ultima actualizacion: 2026-09-06*
