# PRD — Jarvis de Desarrollo: Asistente de Voz para Agentes de IA y Sistema

**Documento**: Evaluación de alternativas (build vs. adapt) — v1.1 (alcance ampliado: OpenCode + sistema + web + archivos)
**Fecha**: 2026-08-13
**Estado**: EVALUACIÓN — enfoque APROBADO (Opción A: build a medida). **Spike técnico Linux COMPLETADO** (S1 ✅ S2 ✅ S3 ✅ sistema/web/archivos ✅; pendiente S4/WSL2 desde Windows).
**Autor**: A. Borra (con asistencia de orquestador)

---

## 1. Resumen ejecutivo

El usuario quiere un asistente de voz estilo "Jarvis" que le permita dictar órdenes durante su trabajo de desarrollo de sistemas **y también operar su máquina y el entorno**, con casos de uso concretos como:

- "Abrí OpenCode y setealo de tal manera"
- "Preguntale tal cosa"
- "Ayudame a armar un PRD para este tipo de proyecto"
- "Cerrá Linux"
- "Creá un documento tal"
- "Buscá en internet tal cosa"

Se analizaron **60.659 repos** de GitHub llamados "jarvis" y en profundidad los 10 más relevantes por estrellas. **Conclusión principal: no existe un proyecto que haga exactamente este trabajo listo para usar.** Los "jarvis" existentes se dividen en tres familias (asistentes de voz personales, frameworks de investigación de agentes LLM, y herramientas de desarrollo homónimas sin IA) y ninguno está especializado en controlar un agente de código como OpenCode por voz ni en combinar eso con acciones del sistema operativo.

La decisión no es trivial: hay una opción "adaptar" razonable (isair/jarvis) y una opción "construir" que, por la naturaleza del caso (un puente delgado voz → intérprete → acciones), puede ser **menos costosa de lo que parece**. Este documento pondera ambas contra las prioridades declaradas del usuario.

**Prioridades declaradas (ponderación):**
1. **Integración con OpenCode** — 40%
2. **Calidad de voz y latencia** — 35%
3. **Plataforma: Linux nativo + Windows/WSL2** — 15%
4. **Privacidad local** — 10%

---

## 2. Contexto y problema

### 2.1 El problema
En el flujo de desarrollo diario, el usuario alterna entre pensar, investigar y operar herramientas de IA (OpenCode, agentes, SDD) y tareas de la máquina (apagar el sistema, crear archivos, buscar en la web). El cuello de botella es la **interacción manual**: escribir prompts largos, navegar TUIs, configurar agentes, ejecutar comandos de sistema. El usuario quiere dictar esas órdenes por voz como le dictaría a un asistente humano, y que el asistente las ejecute sobre su stack de IA y sobre su sistema operativo.

### 2.2 Por qué no es un problema resuelto
- Los asistentes de voz comerciales (Alexa, Siri, Google) no pueden operar una CLI de agente de código ni ejecutar comandos arbitrarios del sistema.
- Los "jarvis" open source personales se enfocan en chat de voz, home automation o tareas triviales; ninguno orquesta agentes de desarrollo Y acciones del sistema en un solo flujo.
- Los agentes de código (OpenCode, Claude Code, Cursor) tienen interfaces de texto; la mayoría no tiene modo voz nativo.
- El valor real no es el reconocimiento de voz (problema resuelto con Whisper/vosk), sino el **puente semántico**: voz → intérprete → acción sobre el agente o el sistema.

### 2.3 Supuestos a validar en la fase de evaluación técnica
- S1: OpenCode expone CLI invocable por terceros (`opencode run` / sesiones / MCP). → **VALIDADO en spike (2026-08-14)**: `opencode run --dir <repo> --format json` devuelve eventos JSON parseables con sessionID; también `serve`+`attach` y protocolo ACP.
- S2: El reconocimiento de voz local (Whisper.cpp) en Linux da latencia < 2s con calidad aceptable en español. → **VALIDADO con voz real (2026-08-14)**: Whisper small beam1 4.0s (con VAD ~2.5-3s, cerca del objetivo) transcribe "Jarvis" correctamente; medium da transcripción perfecta pero ~9.5s (requiere GPU). Piper con voz es_AR-daniela funciona.
- S3: El usuario prefiere comandos por voz de alto nivel ("armá un PRD") en lugar de comandos textuales exactos, y cada pedido debe iniciar con una palabra clave de activación para no confundirse con otras voces del ambiente. → confirmado en entrevista inicial.
- S4: WSL2 puede acceder a OpenCode instalado en Windows nativo o requiere instancia Linux. → **pendiente: validar desde Windows**.

---

## 3. Usuario objetivo y casos de uso

### 3.1 Perfil
- Desarrollador senior de sistemas (15+ años), stacks PHP/JS y arquitectura de software.
- Trabaja en Linux nativo y Windows + WSL2.
- Usa OpenCode como agente principal de IA, con flujos SDD (spec-driven development).
- Valora velocidad de ejecución y precisión; rechaza fricción y setup frágil.

### 3.2 Persona / Situaciones
| Situación | Ejemplo de orden dictada |
|---|---|
| Iniciar sesión de trabajo | "Abrí OpenCode en el repo anubis-api" |
| Configurar contexto | "Setéalo en modo SDD con artifacts en engram" |
| Pregunta de investigación | "Preguntale cómo funciona el middleware de auth" |
| Generación de artefacto | "Ayudame a armar un PRD para un jarvis de voz" |
| Implementación | "Pedile que implemente la migración 076 con TDD" |
| Revisión | "Que revise el último commit y me diga los riesgos" |
| Sistema | "Cerrá Linux" / "Reiniciá la máquina" |
| Apagar/encender asistente | "Jarvis, apagate" (voz) / atajo o UI (ambas direcciones) |
| Archivos | "Creá un documento con el resumen del sprint" |
| Web | "Buscá en internet qué es tal librería" |

> **Regla de activación**: todas las órdenes se inician con una palabra clave (por defecto "Jarvis", configurable). Sin la palabra clave, el audio se ignora — así el asistente no reacciona a otras voces ni conversaciones del ambiente.

> **Switch on/off** (RF-11): el asistente completo se puede apagar (no escucha, no graba) y encender. El encendido es siempre por vía no vocal (atajo, comando o UI); el apagado puede ser por voz ("Jarvis, apagate") o por la misma vía no vocal.

### 3.3 Flujo de interacción objetivo
```
Voz (micrófono) → [detección de palabra clave] → [STT local] → texto → [intérprete de órdenes] → acción
                                              ├── OpenCode (agente/CLI)
                                              ├── Sistema (apagar, reiniciar, apps)
                                              ├── Archivos (crear/editar documentos)
                                              └── Web (búsqueda, apertura de URL)
                                              ↓
                        respuesta hablada ← [TTS] ← resumen de resultado
```

---

## 4. Requisitos

### 4.1 Funcionales (RF)
- **RF-1** Dictado por voz con **palabra clave de activación obligatoria** ("Jarvis" por defecto, configurable): cada pedido debe comenzar con la palabra clave; el audio sin ella se ignora, evitando confusión con otras voces en el ambiente.
- **RF-2** Traducción de órdenes de voz a invocaciones de OpenCode (CLI/agente).
- **RF-3** Soporte de comandos de alto nivel: abrir repo, configurar agente, preguntar, pedir PRD/artefacto, implementar tarea, revisar cambio.
- **RF-4** Lectura hablada de respuestas/resúmenes (TTS).
- **RF-5** Confirmación verbal antes de acciones destructivas (commits, push, borrado, **apagado/reinicio**).
- **RF-6** Persistencia de sesión y contexto del proyecto activo.
- **RF-7** Funcionamiento en Linux nativo y Windows/WSL2.
- **RF-8** Control del sistema: apagar, reiniciar, cerrar sesión, abrir aplicaciones (con confirmación para acciones destructivas).
- **RF-9** Gestión de archivos: crear documentos de texto/markdown, abrir archivos y carpetas.
- **RF-10** Búsqueda web y apertura de URLs en navegador, con resumen hablado del resultado cuando aplique.
- **RF-11** **Switch on/off** para habilitar/deshabilitar el asistente completo: apagado → no escucha, no graba ni reacciona a la palabra clave (modo dormido, ahorro de recursos y privacidad); encendido → vuelve a escuchar. Debe poder reactivarse por una vía **no vocal** (atajo de teclado, comando, ícono/UI o señal externa), porque estando dormido no oye la palabra clave; por voz solo puede **apagarse** ("Jarvis, apagate"), nunca reactivarse a sí mismo.

### 4.2 No funcionales (RNF)
- **RNF-1 (crítico)** Latencia voz→acción: objetivo < 3 s, aceptable < 6 s.
- **RNF-2 (crítico)** Precisión STT en español rioplatense: objetivo > 90% WER.
- **RNF-3** Privacidad: procesamiento de voz local por defecto; nube solo si el usuario lo habilita.
- **RNF-4** Robustez: si la orden no se entiende, repreguntar (nunca ejecutar a medias).
- **RNF-5** Mantenibilidad: menos de 5 componentes de runtime (microfonía, STT, intérprete, orquestador, TTS).

---

## 5. Alternativas evaluadas

### Opción A — Construir a medida: "voz → acciones" (build)
Un puente delgado: STT local (Whisper.cpp / vosk) → intérprete de intenciones (rule-based o LLM) → ejecutor de acciones (OpenCode CLI, comandos de sistema, archivos, web) → TTS (Piper/Coqui).

| Criterio | Valoración |
|---|---|
| Integración OpenCode | **Total** — se diseña para OpenCode desde el día 1 |
| Alcance sistema/web | **Total** — el ejecutor de acciones es extensible por diseño (plug-ins por dominio) |
| Calidad de voz | Alta — se elige el mejor STT local |
| Latencia | Controlable — sin capas heredadas |
| Esfuerzo estimado | 3–5 semanas para MVP utilizable (alcance ampliado) |
| Riesgo | Medio — el intérprete de órdenes es la parte no trivial |
| Mantenimiento | Totalmente bajo control |

**Ventajas**: cubre exactamente el caso; sin deuda ajena; sin depender de la dirección de un proyecto externo.
**Desventajas**: hay que construir el intérprete y la integración desde cero; el TTS/STT requiere tuning inicial.

### Opción B — Adaptar isair/jarvis
Repo de 1.6k★, asistente de voz 100% local con MCP, memoria y dictado. El candidato de adaptación más fuerte.

| Criterio | Valoración |
|---|---|
| Integración OpenCode | Posible vía MCP (integración nativa de herramientas) pero requiere desarrollo; hoy es voice-only sin chat y sin foco en dev |
| Calidad de voz | Alta en macOS (desarrollo primario); **Linux/Windows quedan atrás** ("may lag behind") |
| Latencia | Buena en general |
| Esfuerzo estimado | 2–4 semanas + curva de aprendizaje del codebase |
| Riesgo | Alto — dependencia de un proyecto activo con foco en macOS |
| Mantenimiento | Bajo control; hereda decisiones del upstream |

**Ventajas**: STT/TTS/memoria/MCP ya resueltos y probados; comunidad y evals.
**Desventajas**: plataforma primaria macOS (choque directo con la prioridad de plataforma del usuario); arquitectura orientada a "tercera persona en la sala", no a operar agentes de dev.

### Opción C — Adaptar OpenJarvis (Stanford)
Framework local-first de 8.6k★, activo (actualizado 13-08-2026), con GUI multiplataforma.

| Criterio | Valoración |
|---|---|
| Integración OpenCode | No nativa; es framework de IA local (chat/razonamiento), no de control de agentes de dev; extensible pero requiere desarrollo |
| Calidad de voz | No es su foco principal |
| Latencia | Depende del modelo local elegido |
| Esfuerzo estimado | 4–8 semanas (plataforma grande, curva alta) |
| Riesgo | Medio-alto — construir sobre un framework académico en evolución |
| Mantenimiento | Dependiente del upstream Stanford |

**Ventajas**: infraestructura local-first seria, roadmap, comunidad.
**Desventajas**: sobredimensionado para el caso; no resuelve el puente hacia OpenCode.

### Opción D — Adaptar Priler/jarvis
Rust/Tauri offline, 2.9k★.

| Criterio | Valoración |
|---|---|
| Integración OpenCode | No nativa |
| Calidad de voz | WIP; solo ruso hoy |
| Esfuerzo estimado | Alto (Rust + Tauri + NLU sin implementar) |
| Riesgo | Alto — WIP |
| Mantenimiento | Bajo control |

**Desventajas dominantes**: solo ruso, NLU sin implementar, proyecto experimental. **Descartada.**

### Opción E — Alternativas no-jarvis (dictado + shell)
Usar dictado del sistema (Whisper + atajos) y pegar texto en OpenCode, o usar voice-mode de otros agentes.

| Criterio | Valoración |
|---|---|
| Integración OpenCode | Frágil — dictado pega texto; no ejecuta acciones estructuradas |
| Esfuerzo estimado | Horas |
| Riesgo | Bajo pero valor limitado |
| **Conclusión** | Útil como *stopgap*, no como solución. |

---

## 6. Matriz de decisión ponderada

Ponderación según prioridades: OpenCode (40%) · voz/latencia (35%) · plataforma (15%) · privacidad (10%). Escala 1–5.

| Criterio (peso) | A: Build | B: isair | C: OpenJarvis | D: Priler | E: Dictado |
|---|---|---|---|---|---|
| Integración OpenCode (40%) | 5 | 3 | 2 | 1 | 2 |
| Voz y latencia (35%) | 4 | 4 | 3 | 2 | 3 |
| Plataforma Linux/WSL2 (15%) | 5 | 2 | 4 | 3 | 5 |
| Privacidad local (10%) | 5 | 5 | 4 | 5 | 4 |
| **Puntaje ponderado** | **4.75** | **3.30** | **2.75** | **1.95** | **3.05** |

**Resultado preliminar: Opción A (build) lidera con claridad**, seguida de B (adaptar isair/jarvis) y E (dictado como stopgap).

---

## 7. Recomendación preliminar

**Construir un MVP delgado "voz → acciones" (Opción A), reutilizando componentes open source de voz** (Whisper.cpp para STT, Piper para TTS), **y un intérprete de órdenes mínimo** que inicialmente cubra 5–6 comandos de alto nivel de OpenCode (abrir repo, configurar agente, preguntar, armar PRD, implementar, revisar) más las acciones de sistema (apagar/reiniciar con confirmación), archivos (crear documento) y web (buscar).

Razones:
1. La integración con OpenCode es la prioridad #1 y solo el build la garantiza sin fricción.
2. El build es un puente, no un asistente completo: no hay que reimplementar STT/TTS (existen libs maduras), solo el intérprete y el ejecutor de acciones.
3. El ejecutor de acciones por dominio (OpenCode, sistema, archivos, web) es extensible y permite crecer el alcance sin rediseñar.
4. isair/jarvis es atractivo pero su debilidad en Linux/Windows choca frontalmente con el entorno real del usuario (prioridad ponderada).
5. El dictado plano (E) puede servir como *stopgap* inmediato mientras se construye el MVP.

**Puerta de decisión**: validar primero los supuestos S1–S4 con un spike técnico de 1–2 días antes de comprometer el build completo.

---

## 8. Riesgos y mitigaciones

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Intérprete de órdenes no entiende variaciones del habla natural | Alta | Medio | Empezar con comandos fijos + repregunta; LLM para desambiguar después |
| Latencia de STT local en HW actual | Media | Alto | Medir en spike; fallback a API de nube opcional |
| OpenCode no expone la API de control esperada | Media | Alto | Spike S1 antes de decidir; alternativa: emular teclado |
| WSL2/audio: microfonía en dos entornos | Media | Medio | Probar en ambos; foco primero en Linux nativo |
| Mantenimiento del build propio | Media | Medio | Diseño con < 5 componentes; documentar; evitar sobre-ingeniería |

---

## 9. Métricas de éxito (para el MVP)

- **M1** % de órdenes dictadas ejecutadas correctamente sin re-escritura manual: ≥ 70% en el primer mes.
- **M2** Latencia media voz → primera acción visible: < 6 s.
- **M3** Precisión STT en español rioplatense: ≥ 90% WER.
- **M4** Sin regresión de flujo: el usuario sigue usando OpenCode normalmente si el Jarvis falla (degradación segura).
- **M5** Cobertura de dominios: las 4 categorías de acción (OpenCode, sistema, archivos, web) funcionan en el MVP sin errores de ejecución bloqueantes.
- **M6** Confirmaciones: 100% de las acciones destructivas (apagado, borrado, push) piden confirmación verbal antes de ejecutarse.

---

## 10. Decisiones pendientes y próximos pasos

1. **Aprobar el enfoque** (build vs. adaptar vs. stopgap) — decisión del usuario con base en la matriz. → **APROBADO: Opción A (build)**.
2. **Spike técnico (1–2 días)** — **COMPLETADO en Linux (2026-08-14)**:
   - S1 validado: interfaz de control de OpenCode (CLI run + serve/attach + ACP).
   - S2 validado: Whisper.cpp small beam1 ~4.0s (VAD → ~2.5-3s) con "Jarvis" bien reconocido; Piper es_AR-daniela OK; medium perfecto pero lento (GPU recomendada).
   - S4: pendiente validar audio y acceso WSL2 desde Windows.
   - Sistema/web/archivos validados en Linux (xdg-open + polkit).
3. Si el spike pasa → **definir alcance del MVP** (qué comandos, qué TTS, qué UX) y recién ahí abrir el ciclo SDD (spec → design → tasks → apply). → **El spike pasó en Linux; definir alcance del MVP + validar S4.**
4. Considerar el dictado plano como *stopgap* inmediato mientras tanto.

---

## Apéndice A — Repos "jarvis" analizados (resumen)

| Repo | ★ | Familia | Relevancia |
|---|---|---|---|
| microsoft/JARVIS (HuggingGPT) | 25.1k | Investigación LLM | Histórico; no aplica (requiere 24GB VRAM, reconstrucción desde 2023) |
| open-jarvis/OpenJarvis | 8.6k | Framework local-first | Referencia técnica, sobredimensionado |
| zouhir/jarvis | 5.5k | Dev tool (webpack) | Homónimo; no aplica |
| sukeesh/Jarvis | 3.6k | Asistente CLI sin IA | No aplica (sin IA) |
| Priler/jarvis | 2.9k | Voz offline Rust | WIP, solo ruso |
| ascending-llc/jarvis-registry | 2.8k | Gateway MCP enterprise | No aplica (infra enterprise) |
| isair/jarvis | 1.6k | Voz local + MCP | Candidato de adaptación (Opción B) |
| swapagarwal/JARVIS-on-Messenger | 1.4k | Bot Messenger | No aplica |
| kishanrajput23/Jarvis-Desktop-Voice-Assistant | 876 | Asistente desktop Python | Hobby, no dev-agent |
| alexylem/jarvis | 848 | Voz home automation (RPi) | No aplica |

---
*Este documento es de evaluación y no compromete implementación. La matriz y recomendaciones se revisarán tras el spike técnico.*
