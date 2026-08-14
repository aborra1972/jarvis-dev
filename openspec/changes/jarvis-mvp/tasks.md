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
- [ ] 1.1 `pyproject.toml` (scripts jarvis, pytest ini, deps) + `jarvis/.venv` install; strict_tdd→true
- [ ] 1.2 `tests/{unit,integration,fixtures}` + conftest; `cli.py` stubs + `config.py` (paths, ports, allowlists)
- [ ] 1.3 Signal: pytest green + `jarvis --help`

## Phase 2: Interpreter
- [ ] 2.1 RED: golden/normalize tables ("cerrá linux", "apagate", "abrí/abrime")
- [ ] 2.2 `interpreter/normalize.py` (accents, wake-strip)
- [ ] 2.3 `interpreter/golden.py` regex gate; LLM rejection ("cerrá la ventana")
- [ ] 2.4 `schema.py` + `llm.py` fake-provider tests: happy/unknown→re-ask
- [ ] 2.5 Corpus replay tests (M1/M3)

## Phase 3: Orchestrator
- [ ] 3.1 `orchestrator/state.py` FSM + transition tests
- [ ] 3.2 `confirm.py` 15s (injectable clock): sí/no/timeout abort (M6)
- [ ] 3.3 Re-ask ×2→reveal (RNF-4) in `session.py`
- [ ] 3.4 `session.py`: active project (git cwd→last-repo), repo→{port, sessionIDs}
- [ ] 3.5 `supervisor.py`: health/restart (3/min), timeouts 15s/20s, degrade (M4)

## Phase 4: Executors
- [ ] 4.1 `actions/base.py`: Executor Protocol + registry
- [ ] 4.2 RED: opencode fake-server tests (health, attach, JSON)
- [ ] 4.3 `actions/opencode.py`: serve + 6 commands; RED: `";rm -rf /"` rejected
- [ ] 4.4 `actions/system.py`: shutdown/reboot, allowlist; RED: disallowed/no shell
- [ ] 4.5 `actions/files.py`: create_doc new-only, open_file_dir
- [ ] 4.6 `actions/web.py`: search/open_url; RED: bad URL rejected
- [ ] 4.7 `actions/assistant_lifecycle.py`: power_off_self, help, cleanup
- [ ] 4.8 Integration (slow): real serve + `run --attach`

## Phase 5: Voice + Apply Gates
- [ ] 5.1 `audio.py`: sounddevice 16kHz, VAD, 800ms-silence, fallback
- [ ] 5.2 `wake.py`: openWakeWord (hey_jarvis + jarvis.onnx); no self-trigger
- [ ] 5.3 `stt.py`: whisper-cli (es, beam1, VAD, --prompt, 15s)
- [ ] 5.4 `tts.py`: piper es_AR-daniela + queue (20s)
- [ ] 5.5 GATE q5-medium: ≤4s CPU→promote; record
- [ ] 5.6 GATE wake: train jarvis.onnx; promote if beats hey_jarvis; record
- [ ] 5.7 Integration (slow): real whisper/piper; offline degrade

## Phase 6: E2E + Polish
- [ ] 6.1 `orchestrator/loop.py`: capture→STT→interpreter→executor→TTS; ack >3s
- [ ] 6.2 E2E demo: open repo→ask→shutdown + M1/M3 replay + latency
- [ ] 6.3 `jarvis clean`; switch off (no mic); non-vocal on (RF-11); verify M4/M5/M6; README
