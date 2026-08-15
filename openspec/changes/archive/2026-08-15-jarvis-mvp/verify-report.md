```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:98a9eb8c8867c0f8e51be25a6ab983b59248392750794348dd54269f3950cd0d
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 25/25
scenarios: 51/51
test_command: jarvis/.venv/bin/pytest jarvis/tests -q
test_exit_code: 0
test_output_hash: sha256:8b8c2f228bb3b661afebf0a640636a6a8db160558bf2a7b5a8f30dd084d5d489
build_command: jarvis/.venv/bin/python -m compileall -q jarvis/src
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# Re-verificación tras remediación — change `jarvis-mvp`

**Fecha**: 2026-08-15 · **Modo**: Standard (strict_tdd no persistido en config/cache) · **Base**: HEAD `77997fa` (fixes `1020c40` + `77997fa` sobre `ad3f20f`).

## Resumen ejecutivo

Re-verificación del verify previo que reportó FAIL (2 CRITICAL). **Ambos CRITICAL están RESUELTOS**: (1) ack hablado "dale, te aviso cuando esté" ANTES de `execute()` para intents long-running (ask/create_artifact/implement/review), probado con un test que aserta el ORDEN ack→execute→resultado; (2) `create_doc` captura `OSError` y responde error hablado sin crashear el loop, manteniendo intacto el caso FileExistsError ("ya existe"). Sin regresiones: **530 tests unit/integración verdes + 3 e2e reales verdes** (whisper STT, piper TTS+paplay, opencode serve/attach roundtrip), 33/33 tareas, compileall OK. **Veredicto: PASS WITH WARNINGS** — quedan 4 escenarios PARTIAL (doble feedback sin eco de texto, métricas de latencia/WER proxy-only) y 4 WARNINGs ya conocidos del verify previo, ninguno introducido por los fixes. **next_recommended: archive listo** (0 blockers, 0 critical).

## Veredicto sobre los 2 CRITICALs previos

### CRITICAL-1 — Ack hablado pre-ejecución para ops >3s → **RESUELTO**
- **Fix**: commit `1020c40` — `loop.py:50` define `LONG_OPERATION_ACK = "dale, te aviso cuando esté"`; `loop.py:189-190` habla el ack ANTES de `pipeline.executor.execute()` cuando `_is_long_running(executor, intent.intent)`; `opencode.py:LONG_RUNNING_INTENTS = {ask, create_artifact, implement, review}`; `base.py:73,94` expone `registry.long_running_intents`.
- **No-bloqueante**: `PiperSpeaker.speak` (pipeline.py:121-124) encola y vuelve; el worker thread (pipeline.py:101-111) sintetiza/reproduce mientras la operación corre hasta 30s → el ack suena ANTES del resultado.
- **Tests que cubren el escenario "Long LLM operation"** (orden ack→execute→resultado, verdes en la corrida real):
  - `test_loop.py::test_long_llm_operation_speaks_ack_before_executing` — `TrackingExecutor` registra lo que el speaker ya había dicho cuando corrió `execute()`; aserta `spoken_before_execute == [LONG_OPERATION_ACK]` y secuencia final `[ACK, "listo, implementé el login"]`. ✅
  - `test_loop.py::test_short_operation_speaks_no_ack` — intent no long-running NO emite ack (sin ruido). ✅
  - `test_actions_base.py::test_build_registry_marks_opencode_work_intents_long_running` — el registry marca exactamente los 4 intents LLM. ✅

### CRITICAL-2 — `create_doc` crasheaba con path inválido → **RESUELTO**
- **Fix**: commit `77997fa` — `files.py:34-38` captura `OSError` DESPUÉS de `FileExistsError` (precedencia correcta: FileExistsError es subclase de OSError) y devuelve `ActionResult(ok=False, spoken="no pude crear el documento")`; cubre dir padre faltante, proyecto no escribible y nombre reservado.
- **Tests que cubren el escenario "Invalid path"** (verdes en la corrida real):
  - `test_actions_files.py::test_create_doc_invalid_project_path_reports_spoken_error` — path es un archivo → `ok=False`, spoken de error, nada creado. ✅
  - `test_actions_files.py::test_create_doc_missing_parent_dir_reports_spoken_error` — dir padre inexistente → idem. ✅
  - `test_loop.py::test_create_doc_invalid_path_degrades_to_spoken_error` — loop completo NO crashea: outcome `"failed"`, último spoken contiene "no pude crear". ✅
- **Caso FileExistsError intacto**: `test_create_doc_never_overwrites_existing_file` aserta "ya existe" y contenido original sin modificar. ✅

## Resultados de pytest (reales, HEAD 77997fa)

| Comando | Resultado | Exit | Output hash |
|---|---|---|---|
| `jarvis/.venv/bin/pytest jarvis/tests -q` | **530 passed, 3 deselected in 4.52s** | 0 | `8b8c2f22…` |
| `jarvis/.venv/bin/pytest jarvis/tests -m e2e -q` | **3 passed, 530 deselected in 21.99s** | 0 | `c8cf1823…` |
| `jarvis/.venv/bin/python -m compileall -q jarvis/src` | OK (sin salida) | 0 | `e3b0c442…` (vacío) |

E2E reales (binarios de `spike/` presentes): `test_e2e_whisper_stt_small_timing`, `test_e2e_piper_tts_and_paplay_playback`, `test_e2e_opencode_serve_attach_roundtrip`. Tests puntuales de los fixes: **7/7 passed** (`test_loop` ×4, `test_actions_files` ×3, `test_actions_base` ×1). `evidence_revision` = SHA-256 sobre los bytes exactos concatenados de los 3 outputs de comando (unit + e2e + build).

## Matriz de cumplimiento (25 requisitos / 51 escenarios)

Leyenda: ✅ COMPLIANT · ⚠️ PARTIAL · ❌ UNTESTED/FAILING — **51 escenarios con test de cobertura pasando (47 ✅ full + 4 ⚠️ con cobertura parcial)**

### voice-pipeline — 5 req, 11 scen → 7 ✅ / 4 ⚠️
| Escenario | Estado | Evidencia |
|---|---|---|
| Activation | ✅ | test_loop.test_executes_open_app_cycle; test_audio_pipeline.test_loop_listening_uses_capturer_wake_and_stt |
| False activation from ambient voice | ✅ | test_audio_wake (threshold); test_loop.test_no_wake |
| Noise rejection | ✅ | test_audio_capture.gather_empty; test_utterance_capture_returns_none_on_pure_silence |
| Configurable wake word | ✅ | test_audio_wake.test_explicit_model_paths_are_preserved; WAKE_CUSTOM_MODEL |
| Correct transcription | ⚠️ | e2e whisper transcribe real; aserta solo no-vacío |
| Domain prompt bias | ⚠️ | test_audio_stt aserta `--prompt`; sin aserción de precisión |
| STT failure | ✅ | test_audio_pipeline.test_loop_speaks_error_when_stt_fails_and_keeps_listening |
| Dual feedback | ⚠️ | spoken ✅; **texto en pantalla inexistente** (WARNING-1) |
| Non-LLM command within budget | ⚠️ | solo timing de STT en e2e, no pipeline completo |
| **Long LLM operation** | ✅ **→COMPLIANT** | `test_long_llm_operation_speaks_ack_before_executing` (ordena ack→execute→resultado) + `test_short_operation_speaks_no_ack` + `test_build_registry_marks_opencode_work_intents_long_running` (antes ❌ CRITICAL-1) |
| Assistant speaking (no self-trigger) | ✅ | test_audio_pipeline.test_loop_drops_wake_while_speaker_is_playing |

### command-interpreter — 4 req, 9 scen → 9 ✅
| Escenario | Estado | Evidencia |
|---|---|---|
| Happy path | ✅ | test_interpreter.test_llm_happy_path |
| Rioplatense variants | ✅ | test_corpus.test_golden_corpus_replay; golden fast path |
| Unknown command | ✅ | test_interpreter.test_unknown_intent_triggers_reask |
| Golden table confirms | ✅ | test_interpreter.test_golden_destructive_never_consults_llm; test_metrics M6 |
| LLM misinterpretation rejected | ✅ | test_interpreter.test_llm_destructive_suggestion_rejected_by_golden |
| Ambiguous destructive | ✅ | test_interpreter.test_ambiguous_destructive_never_emitted |
| Destructive out-of-scope (no shell) | ✅ | unsupported path; grep shell=True = 0 |
| Re-ask resolves | ✅ | test_confirm + flow next_step |
| Two failed re-asks reveal | ✅ | test_loop.test_reask_twice_then_reveal_transcript |

### opencode-control — 4 req, 10 scen → 10 ✅
| Escenario | Estado | Evidencia |
|---|---|---|
| Ask reuses existing session | ✅ | test_actions_opencode.test_ask_reuses_bound_session + e2e serve/attach |
| Server recovery | ✅ | test_server_manager_* (spawn/degrade/ensure_healthy) |
| open_repo | ✅ | test_open_repo_*; test_loop con repo explícito sin proyecto activo |
| configure | ✅ | test_configure_writes_agents_md |
| implement without active project | ✅ | NO_ACTIVE_PROJECT path |
| create_artifact | ✅ | test_run_intent_builds_opencode_command_per_intent |
| review | ✅ | test_run_intent_builds_opencode_command_per_intent |
| Startup detection | ✅ | test_session.test_start_detects_active_project_via_git / keeps_last_known |
| Voice switch active project | ✅ | test_session.test_switch_active_project |
| Offline degradation | ✅ | test_metrics.test_m4_opencode_degrades_to_spoken_notice |

### system-control — 3 req, 6 scen → 6 ✅
| Escenario | Estado | Evidencia |
|---|---|---|
| Confirmed shutdown/reboot | ✅ | test_loop.test_confirm_yes_executes_shutdown; test_shutdown_runs_systemctl_poweroff |
| Refused | ✅ | test_loop.test_confirm_no_aborts_without_executing |
| Timeout aborts | ✅ | test_loop.test_confirm_silence_times_out; 15s clock |
| Allowed app | ✅ | test_open_app_allowlisted_spawns_xdg_open |
| Disallowed app | ✅ | test_open_app_disallowed_is_rejected; unknown app rejected |
| Shell-like request rejected | ✅ | unsupported + no shell=True |

### file-management — 2 req, 4 scen → 4 ✅ (antes 3 ✅ / 1 ❌)
| Escenario | Estado | Evidencia |
|---|---|---|
| New file | ✅ | test_create_doc_writes_slugged_name_in_project |
| Overwrite refused | ✅ | test_create_doc_never_overwrites_existing_file ("ya existe", contenido intacto) |
| **Invalid path** | ✅ **→COMPLIANT** | `test_create_doc_invalid_project_path_reports_spoken_error` + `test_create_doc_missing_parent_dir_reports_spoken_error` + `test_loop.test_create_doc_invalid_path_degrades_to_spoken_error` (loop no crashea) (antes ❌ CRITICAL-2) |
| Open folder | ✅ | test_open_file_dir_* |

### web-actions — 2 req, 4 scen → 4 ✅
| Escenario | Estado | Evidencia |
|---|---|---|
| web_search happy path | ✅ | test_web_search_spawns_xdg_open_with_google_url |
| Browser failure | ✅ | safe_run degrade (test_system_failure_degrades_to_spoken_error) |
| open_url valid | ✅ | test_open_url_spawns_xdg_open_with_http_url |
| open_url malformed | ✅ | test_open_url_malformed_is_rejected; non_http_is_rejected |

### assistant-lifecycle — 5 req, 7 scen → 7 ✅
| Escenario | Estado | Evidencia |
|---|---|---|
| Manual start | ✅ | cli start + loop tests |
| Help | ✅ | test_handle_help_lists_all_commands |
| Voice power-off | ✅ | test_power_off_self_logs_and_acknowledges; test_loop.test_power_off_self_stops_loop |
| Switch off stops recording | ✅ | test_loop.test_switch_off_ignores_wake; mic released |
| Non-vocal reactivation | ✅ | test_switch_signal + switch resume |
| Local-only storage | ✅ | test_logs (transcript journal local, preserva state.json) |
| Log cleanup | ✅ | test_logs clean |

## Verificación estática (ADR → código, sin regresión)

| ADR | Estado | Evidencia |
|---|---|---|
| ADR-1 opencode serve persistente + attach + sessionID | ✅ | actions/opencode.py ServerManager; e2e roundtrip PASS |
| ADR-2 interpreter LLM-first + golden FIRST authoritative | ✅ | interpreter.py:53 golden.gate primero; LLM nunca emite destructivos (test_metrics M6) |
| ADR-3 openWakeWord hey_jarvis + custom gate | ✅ | audio/wake.py; gate registrado, no promovido |
| ADR-4 whisper-cli small `-l es -bs 1` + medium gate | ✅ | audio/stt.py; STT_MEDIUM_PROMOTED False (e2e aserta) |
| ADR-5 piper es_AR-daniela | ✅ | audio/tts.py; e2e TTS+paplay PASS |
| ADR-6 sounddevice streaming + VAD (fallback arecord) | ⚠️ | sounddevice+VAD ✅; fallback arecord ausente (WARNING-3, sin cambios) |
| ADR-7 confirm 15s fail-closed + allowlists + switch SIGUSR1/2 | ✅ | confirm.py:69; allowlists; loop.py |
| ADR-8 sin shell, executors in-process | ✅ | grep `shell=True` = 0; `os.system` = 0; registro in-process |

## Cumplimiento de tasks

33/33 tareas `[x]` en `openspec/changes/jarvis-mvp/tasks.md` — 0 pendientes (fase 1 a 6 completas). Las tasks 6.1 (ack >3s) y 4.5 (create_doc) ahora cumplen sus escenarios de spec con tests.

## TDD / capas

- strict_tdd NO está persistido en config/cache (pyproject solo define pytest ini + markers; no hay `strict_tdd: true` ni apply-progress con TDD Cycle Evidence) → verify en modo **Standard**; no aplican bloqueos de TDD estricto.
- Capas: unit (cubre los fixes en test_loop/test_actions_files/test_actions_base) + e2e real (`-m e2e`). No hay tool de coverage configurada (sin pytest-cov) → cobertura no medida; informativo.
- Assertion quality (fixes): las aserciones nuevas verifican comportamiento real (orden de habla, no-crash, nothing created, spoken de error) — sin tautologías ni aserciones vacías.

## Hallazgos

**CRITICAL**: Ninguno (los 2 previos RESUELTOS; 0 regresiones).

**WARNING** (arrastrados del verify previo, sin cambios, ninguno introducido por los fixes):
- WARNING-1 — Dual feedback: `loop.py:192` solo habla `result.spoken`; no hay eco del resultado como texto en stdout (escenario "Dual feedback" sigue PARTIAL).
- WARNING-2 — Latencia/WER proxy-only (RNF-1 M2 / RNF-2 M3): e2e mide solo STT; sin medición pipeline <6s ni WER sobre corpus.
- WARNING-3 — Fallback arecord de ADR-6 no implementado (grep arecord en src = 0).
- WARNING-4 — `jarvis stop`/`jarvis logs` stubs ("not implemented yet").

**SUGGESTION**:
- `ActionResult.long_running` (contracts.py:50) se setea en opencode.py:224 pero el loop consume `registry.long_running_intents`, nunca el campo del resultado → campo redundante; consumirlo o eliminarlo.
- Re-ask resolves sigue cubierto por composición (sin test único e2e del flujo clarificar→proceder).

## Conclusión

- **Veredicto**: `pass_with_warnings` — 0 blockers, 0 critical; 25/25 requisitos y 51/51 escenarios con test de cobertura pasando en runtime (47 full + 4 con cobertura parcial → WARNING), 530 tests verdes + 3 e2e reales, 33/33 tareas.
- **Los 2 CRITICALs del verify previo están RESUELTOS** con tests que pasan en runtime y cubren exactamente los escenarios "Long LLM operation" e "Invalid path"; el caso FileExistsError y el no-ack para ops cortas quedaron blindados.
- **next_recommended**: **archive listo** — la base está lista para la fase SDD ARCHIVE (sync de deltas de specs y cierre). Los 4 WARNINGs restantes son post-MVP/diferibles; ninguno bloquea.
- `evidence_revision` (HEAD 77997fa): `98a9eb8c…` sobre los bytes canónicos de evidencia (unit+e2e+build).
