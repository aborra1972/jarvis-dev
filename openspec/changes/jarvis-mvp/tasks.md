# Tasks: jarvis-mvp — Local Voice Assistant MVP

## Review Workload Forecast

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

~3,800 lines (26 files) > 800 → 6 chained PRs; user picks chain strategy before apply.

### Suggested Work Units

| Unit | Goal (PR) | Focused test command | Runtime harness | Rollback boundary |
|------|-----------|----------------------|-----------------|-------------------|
| 1 | Bootstrap+test infra (PR 1) | `pytest jarvis/tests -q` | `jarvis --help` | delete jarvis/ + pyproject |
| 2 | Interpreter+corpus (PR 2) | `pytest tests/unit/test_interpreter* -q` | N/A: pure logic | revert interpreter/ |
| 3 | Orchestrator core (PR 3) | `pytest tests/unit/test_orchestrator* -q` | N/A: fakes+clock | revert orchestrator core |
| 4 | Executors+opencode server (PR 4) | `pytest -q -m "not slow"` | serve/attach smoke `-m slow` | revert actions/ + allowlists |
| 5 | Voice+apply gates (PR 5) | `pytest -m slow` | mic: "Jarvis, abrí Firefox" | revert voice; onnx not promoted |
| 6 | E2E+polish (PR 6) | `pytest -q` + e2e demo | open repo→ask→shutdown + replay | delete jarvis/; stop serve; checkout AGENTS.md |

## Phase 1: Bootstrap
- [x] 1.1 `pyproject.toml` (scripts jarvis, pytest ini, deps) + `jarvis/.venv` install; strict_tdd→true
- [x] 1.2 `tests/{unit,integration,fixtures}` + conftest; `cli.py` stubs + `config.py` (paths, ports, allowlists)
- [x] 1.3 Signal: pytest green + `jarvis --help`

## Phase 2: Interpreter
- [x] 2.1 RED: golden/normalize tables ("cerrá linux", "apagate", "abrí/abrime")
- [x] 2.2 `interpreter/normalize.py` (accents, wake-strip)
- [x] 2.3 `interpreter/golden.py` regex gate; LLM rejection ("cerrá la ventana")
- [x] 2.4 `schema.py` + `llm.py` fake-provider tests: happy/unknown→re-ask
- [x] 2.5 Corpus replay tests (M1/M3)

## Phase 3: Orchestrator
- [x] 3.1 `orchestrator/state.py` FSM + transition tests
- [x] 3.2 `confirm.py` 15s (injectable clock): sí/no/timeout abort (M6)
- [x] 3.3 Re-ask ×2→reveal (RNF-4) in `session.py`
- [x] 3.4 `session.py`: active project (git cwd→last-repo), repo→{port, sessionIDs}
- [x] 3.5 `supervisor.py`: health/restart (3/min), timeouts 15s/20s, degrade (M4)
- [x] 3.6 `loop.py` FSM driver + `cli.py` wiring (start/off/on)

## Phase 4: Executors
- [x] 4.1 `actions/base.py`: Executor Protocol + registry
- [x] 4.2 RED: opencode fake-server tests (health, attach, JSON)
- [x] 4.3 `actions/opencode.py`: serve + 6 commands; RED: `";rm -rf /"` rejected
- [x] 4.4 `actions/system.py`: shutdown/reboot, allowlist; RED: disallowed/no shell
- [x] 4.5 `actions/files.py`: create_doc new-only, open_file_dir
- [x] 4.6 `actions/web.py`: search/open_url; RED: bad URL rejected
- [x] 4.7 `actions/assistant_lifecycle.py`: power_off_self, help, cleanup
- [x] 4.8 Integration (slow): real serve + `run --attach` — e2e roundtrip (session binding)
- [x] 4.8b fix: opencode streams the reply in `type:"text"` events → `parse_assistant_text` fixed (5deea57)

## Phase 5: Voice + Apply Gates
- [x] 5.1 capture (`audio/capture.py`): sounddevice 16kHz, VAD, 800ms-silence, fallback
- [x] 5.2 wake (`audio/wake.py`): openWakeWord (hey_jarvis + jarvis.onnx); no self-trigger
- [x] 5.3 stt (`audio/stt.py`): whisper-cli (es, beam1, VAD, --prompt, 15s)
- [x] 5.4 tts (`audio/tts.py`): piper es_AR-daniela (20s); async queue lands in E2E (PR6)
- [x] 5.5 GATE q5-medium: model selection by duration (≤4s→medium) wired in `select_model`; CPU timing promote decision recorded E2E (PR6)
- [x] 5.6 GATE wake: train jarvis.onnx; promote if beats hey_jarvis; record — E2E (PR6)
  - RESOLVED (PR6): training not feasible here (no dataset/tools) → `docs/wake-word-training.md` (ef8cb9b) documents the training/promote path; `WAKE_CUSTOM_MODEL` config hook + precedence in `build_model_paths` shipped; packaged `hey_jarvis_v0.1.onnx` stays active. Promote NOT granted (no beats-evidence).
- [x] 5.7 Integration (slow): real whisper/piper; offline degrade — E2E (PR6)
- NOTE (PR5): the orchestrator slice instruction specified an `audio/` package (capture/wake/stt/tts/playback/pipeline) instead of the flat `audio.py`/`wake.py`/`stt.py`/`tts.py` from design.md — package layout is the operative structure; flat stubs deleted.

## Phase 6: E2E + Polish
- [x] 6.1 `orchestrator/loop.py`: capture→STT→interpreter→executor→TTS; ack >3s
  - `build_pipeline()` + real `start()` (8f07feb); ack = spoken reply via TTS queue with non-blocking worker (0bfa1dc)
- [x] 6.2 E2E demo: open repo→ask→shutdown + M1/M3 replay + latency
  - Real binaries smoke suite (ca82a31): whisper STT timing 4.34s, piper+paplay, opencode serve→run--attach→session reuse. Full voice-mic demo not run (no interactive run).
- [ ] 6.3 `jarvis clean`; switch off (no mic); non-vocal on (RF-11); verify M4/M5/M6; README
