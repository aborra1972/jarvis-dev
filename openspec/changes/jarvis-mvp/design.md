# Design: jarvis-mvp — Local Voice Assistant MVP

## Technical Approach

Thin voice→action bridge (PRD Option A; spike S1✅ S2✅ S3✅ system/web/files✅). ONE Python process runs the orchestrator (RNF-5), supervising 3 warm/cold subprocess boundaries: `whisper-cli` (STT, per-utterance), `piper` (TTS, per-response), `opencode serve` (persistent headless, long-lived — kills the ~9s cold start that breaks RNF-1). Executors are in-process modules (`actions/`), not processes. Wake word = openWakeWord (pretrained `hey_jarvis` + custom rioplatense `jarvis.onnx` training gate). Interpreter = LLM-first (routes through the SAME OpenCode server → zero provider setup) with a rule-based golden table as the authoritative hard gate for `shutdown`/`reboot`/`power_off_self`. Voice-first with dual TTS+text feedback; manual `jarvis start`; deletable local logs.

## Architecture Decisions

| # | Decision | Choice | Alternatives | Rationale |
|---|----------|--------|--------------|-----------|
| ADR-1 | OpenCode integration | Persistent headless `serve` + `run --attach` + sessionID reuse, one server per repo, self-managed by orchestrator | Cold `opencode run` per command (~9s — violates RNF-1); ACP protocol (heavier, unvalidated) | Spike S1 validated serve/attach + `--format json` events; warm session makes `ask` 1-4s; zero extra setup. |
| ADR-2 | Interpreter | LLM-first via OpenCode provider (`run --attach` on a dedicated interpreter session, JSON-only prompt); golden regex table is the AUTHORITATIVE gate for destructive intents | Rule-only (rigid, fails free-form rioplatense — RF-2/3); LLM-only (destructive misclassification risk) | Golden runs FIRST: destructive intents never touch the LLM (spec: "never depends on the LLM"); free-form for the other 12. |
| ADR-3 | Wake word | openWakeWord day 1: pretrained `hey_jarvis` + optional custom rioplatense model trained via openwakeword training (Piper-synthetic es_AR samples, Linux-only OK) | VAD+whisper first-token gate (explore suggestion — 2.5s+ per frame, high CPU, slow); Porcupine (closed SDK/licensing) | openWakeWord is local, ~80ms, ~2-5% CPU, drops in `.onnx` (onnxruntime already in spike venv). "Jarvis" is a supported pattern; rioplatense tuning is a decision gate. |
| ADR-4 | STT | whisper-cli small (`-l es -b 1 --vad --prompt <domain>`) default; **q5-medium decision gate** at apply (drop-in quantized gguf, target ≤4s) | medium fp16 (~9.5s CPU — breaks RNF-1); base/tiny (M3 ≥90% WER risk) | Spike: small ≈2.5-3s w/ VAD meets M2; medium perfect but slow; q5_0 ≈2-3x faster than fp16 medium → accuracy win if budget holds. |
| ADR-5 | Process topology | Single Python process + supervised subprocesses (whisper/piper/opencode); in-process executors | systemd units (conflicts with manual-start binding); per-component daemons (breaks RNF-5); MQ/IPC (over-engineering) | 5 runtime components exactly; orchestrator owns lifecycle/health/restart; stdlib threading for capture loop + TTS queue. |
| ADR-6 | Audio capture | sounddevice (system `libportaudio.so.2` already present → zero NEW native deps), streaming 16kHz frames; `arecord` config fallback | Pure arecord (raw ALSA pipes, fragile block handling); pyaudio (same PortAudio, worse API) | Verified `ldconfig` shows PortAudio; sounddevice gives push-style callbacks to feed openWakeWord + VAD directly. |
| ADR-7 | Safety gate | Verbal confirm, 15s timeout, abort on "no"/timeout, for shutdown/reboot/power_off_self (M6); allowlists for apps; no arbitrary shell; create_doc new-only | No confirm (breaks M6); TUI-only confirm (voice-first product); arbitrary shell (explicitly out) | Spec: 100% destructive confirmations (M6); timeout MUST abort; explicit refuse/abort paths tested. |
| ADR-8 | Interpreter transport | Interpret intents through the persistent OpenCode server (dedicated sessionID), not a second provider client | Direct provider API call (requires duplicating OpenCode auth/model config); local small model | Binding decision "usa el proveedor/config de OpenCode (cero setup extra)"; one server, two sessionIDs (interpreter + work). |

## Data Flow

```
 user ──mic──▶ audio.py (16kHz float) ──▶ wake.py (openWakeWord)
                │ trigger                                              supervisor.py
                ▼                                                        │ health/timeout/restart
 capture until 800ms silence ──▶ stt.py ──whisper-cli small──▶ transcript
                                                                        ▼
 tts.py (piper es_AR-daniela) ◀── orchestrator (FSM) ◀── interpreter (LLM→golden gate)
      │                                                                 │
      └── text + spoken ◀── result ◀── actions/* (in-process executors)
                                        ├── opencode.py → opencode serve/run --attach
                                        ├── system.py   → loginctl/polkit, xdg-open (allowlist)
                                        ├── files.py    → create_doc new-only
                                        └── web.py      → xdg-open (validated URL)
```

## Sequence Diagrams

**(a) Full flow: wake → STT → interpreter → executor → TTS**

```
User  audio.py   wake.py    stt.py     interpreter     golden      actions       tts.py
 |--"Jarvis, abrí Firefox"-->|           |             |           |             |
 |      |---frames----------->|          |             |           |             |
 |      |<--trigger-----------|          |             |           |             |
 |      |---capture(silence)-->|---------|             |           |             |
 |      |                    |---transcript----------->|           |             |
 |      |                    |                         |--LLM JSON-->|            |
 |      |                    |                         |<-open_app--|            |
 |      |                    |                         |--golden: n/a (no destr.)-|
 |      |                    |                         |--run(open_app, "firefox")-->|
 |      |                    |                         |<--ok-------|            |
 |      |                    |                         |--speak("listo")---------->|
 |<--"Listo" + text----------|                         |           |             |
```

**(b) Destructive confirm (15s)**

```
User   stt   interpreter  golden   orchestrator(confirming)   actions/system
 |--"cerrá linux"---->|      |        |            |                |
 |      |---transcript-->|    |        |            |                |
 |      |              |--shutdown?-->|            |                |     (golden match)
 |      |              |<--shutdown+confirm_required-->|            |
 |      |              |                |--TTS: "¿confirmás que apago la máquina?"-->|
 |--"sí"-->capture-->transcript-->yes-->|            |                |
 |      |              |                |--15s timer started-->|--execute shutdown-->|
 |      |              |                |<--done     |                |
 |--"no" ou timeout 15s: -->abort-->TTS "ok, no hago nada"-->listening (M6: nothing executed)
```

**(c) Re-ask ×2 + reveal**

```
User        stt      interpreter(LLM)    orchestrator
 |--transcript-->|    confidence 0.3      |
 |      |          |--unknown/uncertain-->|--TTS: "no entendí, ¿podés repetir?" (n=1)
 |--clarification-->| 0.9                 |--proceed execute
 |--ambiguous-->|    0.4 (n=2)            |--TTS: "no te entiendo, repetí una vez más"
 |--still bad-->|    n=3                  |--REVEAL raw transcript on screen + TTS "no pude,
 |      |          |                     |      te muestro lo que escuché" → wait manual input
 |      |          |                     |--NEVER executes partial action (RNF-4)
```

**(d) Switch off → non-vocal reactivation**

```
User     orchestrator   audio.py    mic
 |--"jarvis off" (cmd/UI)-->|        |      (or voice "Jarvis, apagate" after golden+confirm → same stop path)
 |      |--OFF: stop capture-->|--release-->|  no listen, no record (RF-11)
 |      |   (process stays alive, waiting on non-vocal signal)
 |--"jarvis on" (cmd/UI)-->|--ON: restart capture-->|  resume listening
 |--"Jarvis" (voice) DURING off --> IGNORED (no mic open — cannot self-reactivate)
```

**(e) Offline degradation (M4)**

```
User   stt  interpreter  actions/opencode   actions/system
 |--"preguntale X"-->|         |                |
 |      |--ask intent-->|--server down or no network-->|--health-check+restart fails
 |      |                  |--TTS: "necesito red para eso" + text
 |      |                  |   (nothing runs; user's OpenCode workflow unaffected)
 |--"cerrá linux"-->|      |                |--still works (local, no net)-->confirm-->execute
```

## Interpreter (hybrid, safe)

1. **Normalize**: lowercase, strip accents/punctuation, collapse whitespace, strip leading wake-word token(s).
2. **Golden gate FIRST** (deterministic, <1ms, authority over LLM) on normalized transcript:
   - `shutdown`: `^(cerra|apaga) (linux|la maquina|el equipo|el sistema)`
   - `reboot`: `^(reinicia|reiniciar) (linux|la maquina|el equipo|el sistema)`
   - `power_off_self`: `^(apagate|apagame|dormite)( ya| ahora)?$`
   - Match ⇒ emit destructive intent + `confirm_required=true`, LLM NOT consulted. No match ⇒ no destructive intent ever emitted from LLM (spec: golden rejection wins over LLM suggestion).
3. **LLM path** (non-destructive): strict JSON-only system prompt listing the 12 remaining intents + `unknown`; output schema below; confidence threshold 0.6; below ⇒ re-ask ×2 ⇒ reveal raw transcript.
4. **Entities**: LLM-extracted (`repo`, `app`, `query`, `text`, `url`, `engine`) validated per executor (repo must be an existing dir, no shell metachars; URL must parse and be http/https; app must be in allowlist; text free-form for create_doc).

```json
{"intent": "open_repo|ask|configure|create_artifact|implement|review|shutdown|reboot|power_off_self|open_app|create_doc|open_file_dir|web_search|open_url|help|unknown",
 "entities": {"repo": "", "app": "", "query": "", "text": "", "url": "", "engine": "google"},
 "confidence": 0.0}
```

## Orchestrator

- **FSM**: `idle → listening → confirming → executing → speaking → idle`. Wake ⇒ idle→listening; destructive ⇒ confirming (15s timer, yes/no via capture; no/timeout ⇒ abort→idle, M6); re-ask counter (≤2) is session state during listening/confirming; `speaking` drops captured audio (no self-trigger).
- **Session/project (RF-6)**: `~/.local/share/jarvis/state.json` — active project (startup: `git rev-parse` cwd, else last known), repo→{port, sessionID_work, sessionID_interp} map, re-ask counters.
- **Supervisor**: opencode serve — TCP health-check on port, restart with 3/min backoff, failure ⇒ opencode intents degrade to spoken error (M4); whisper-cli — 15s timeout per utterance, non-zero exit ⇒ spoken error; piper — 20s timeout per response; text always shown regardless.
- **Switch (RF-11)**: `jarvis off`/`jarvis on` CLI (non-vocal; off = mic released, nothing recorded); `jarvis start/stop` lifecycle; `jarvis clean` deletes `logs/{transcripts,audio}` (local-only, RNF-3); `power_off_self` lives ONLY in `actions/assistant_lifecycle.py` (binding: single location), golden-gated + 15s confirm.

## OpenCode Integration

- Lifecycle in `actions/opencode.py`: `ensure_server(repo)` → spawn `opencode serve --port <P> --hostname 127.0.0.1` (cwd=repo), poll TCP ready (timeout 15s; cold ≈9s per spike), keep `{repo: port}`.
- Commands: `opencode run --attach http://127.0.0.1:<P> -s <sessionID> --format json --dir <repo> "<prompt>"`; parse JSON events, final assistant text → spoken (truncate ~300 chars) + text. Interpreter uses its own sessionID; work commands (`ask`, `create_artifact`, `implement`, `review`) reuse the work sessionID.
- `open_repo`: ensure server + set active project + announce. `configure`: atomic write of AGENTS.md in ACTIVE repo only (temp+rename; git-rollback safety). `implement` without active project ⇒ re-ask to select (spec).
- Interpreter call rides the same server: `run --attach` with JSON-only prompt (ADR-2/8).

## Wake Word (openWakeWord)

- `audio.py` streams 16kHz mono float via sounddevice; frames (100ms blocks) fed to `Model(wakeword_models=["hey_jarvis", <jarvis.onnx if trained>], inference_framework="onnx", vad_threshold=0.5)`. Trigger ≥ threshold ⇒ capture until 800ms energy silence (max 10s) ⇒ whisper-cli (`--vad` trims wake-word prefix).
- **Tuning gate (apply-time)**: train custom rioplatense "Jarvis" ONNX via openwakeword automatic training (Piper es_AR synthetic samples; Linux OK) using recorded real-voice corpus; promote to default if false-accept/recall beats `hey_jarvis` base on the corpus; decision recorded (proposal: "q5-medium gate decision recorded" pattern). Training is a dev-time tool, not runtime.

## Repo Structure & File Changes

```
jarvis/                         ← new app root (own venv; reuses spike artifacts via config paths)
├── pyproject.toml              Create  package metadata, [project.scripts] jarvis, pytest config
├── src/jarvis/
│   ├── cli.py                  Create  jarvis start/stop/off/on/clean/logs
│   ├── config.py               Create  paths (whisper-cli, piper, models), ports, allowlists, prompt
│   ├── audio.py                Create  sounddevice capture loop + energy VAD (16kHz frames)
│   ├── wake.py                 Create  openWakeWord wrapper (onnx) + threshold
│   ├── stt.py                  Create  whisper-cli subprocess wrapper (es, b1, --vad, --prompt)
│   ├── tts.py                  Create  piper subprocess wrapper (es_AR-daniela), async queue
│   ├── interpreter/
│   │   ├── normalize.py        Create  rioplatense normalization (accents, wake-strip)
│   │   ├── golden.py           Create  destructive regex gate (shutdown/reboot/power_off_self)
│   │   ├── llm.py              Create  JSON-only intent resolution via opencode run --attach
│   │   └── schema.py           Create  intent JSON schema + validation
│   ├── orchestrator/
│   │   ├── state.py            Create  FSM idle/listening/confirming/executing/speaking
│   │   ├── confirm.py          Create  15s verbal confirm gate (yes/no/timeout→abort)
│   │   ├── session.py          Create  active project + repo/session map + re-ask counters
│   │   ├── supervisor.py       Create  health-check/timeout/restart policies
│   │   └── loop.py             Create  wiring: capture→STT→interpreter→executor→TTS
│   └── actions/
│       ├── base.py             Create  Executor Protocol + registry
│       ├── opencode.py         Create  server lifecycle + run/attach + 6 commands (RF-3)
│       ├── system.py           Create  shutdown/reboot (loginctl+polkit), open_app allowlist
│       ├── files.py            Create  create_doc new-only (atomic), open_file_dir
│       ├── web.py              Create  web_search/open_url via xdg-open (validated)
│       └── assistant_lifecycle.py Create power_off_self (ONLY location), help, log cleanup
├── models/                     Create  custom jarvis.onnx (training gate output), openwakeword dir
└── tests/
    ├── unit/                   Create  interpreter/golden/entities/state/confirm/session + actions w/ fakes
    ├── integration/            Create  smoke: real whisper-cli, piper, opencode serve/attach (slow-marked)
    └── fixtures/               Create  rioplatense corpus (recorded, M3 proxy), sample wavs
```

Deps (pyproject): `openwakeword`, `sounddevice`, `numpy`; dev `pytest`. whisper-cli/piper/models referenced from `config.py` pointing at `spike/` artifacts (apply rule: reuse, don't rebuild).

## Interfaces / Contracts

`Executor` Protocol (in-process): `async def execute(ctx: ActionContext, intent: str, entities: dict) -> ActionResult` where `ActionContext` carries `session` (active project, server map), `say(text)` (TTS+text), `confirm_required`, and `ActionResult {ok: bool, spoken: str, data: dict}`. Executors NEVER receive raw transcripts, only validated intents+entities; interpreter owns the allowlist mapping (15 intents).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | normalize, golden gate (matches/rejects/ambiguity), schema validation, rioplatense variants ("abrí/abrime/podés abrir", "cerrá linux", "apagate"), FSM transitions, confirm 15s (injectable clock: yes/no/timeout→abort), re-ask ×2→reveal, session store, executors with fake subprocesses | Table-driven pytest (`tests/unit`); golden table authoritative-over-LLM case (LLM says shutdown, golden rejects ⇒ no emit) |
| Integration | real whisper-cli small transcribes fixture wav; piper produces wav; opencode serve up + `run --attach` returns JSON events; offline path (server down ⇒ degrade message) | `tests/integration`, `@pytest.mark.slow`, real binaries via config paths |
| E2E | `open repo → ask → shutdown(confirm)` demo script; M1/M3 corpus replay (recorded rioplatense commands through interpreter — deterministic); latency timing report | Manual script + `tests/fixtures` replay |

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths | N/A — no executable-doc handling in MVP | — | — |
| Git repository selection | **Applicable** — `open_repo` repo arg + startup detection (`git rev-parse` cwd; `--dir` passed to serve/run) | Repo must be existing dir: `os.path.isdir(realpath)`; reject shell metachars (`;|&$<>`\`) and leading `-`; resolve to absolute path before subprocess | Repo arg `";rm -rf /"`; absolute outside repo; nonexistent dir ⇒ spoken error, no subprocess |
| Commit state | N/A — no git commit automation in MVP | — | — |
| Push state | N/A — no push automation | — | — |
| PR commands | N/A — no PR automation | — | — |
| Subprocess/URL/app args (matrix extension) | **Applicable** — whisper/piper/opencode args, `open_url`, `open_app` | Never interpolate raw audio into args; URL must parse as http/https; app must be in allowlist; xdg-open only for allowlisted/validated targets | Malformed URL; disallowed app ⇒ rejected with spoken msg, nothing spawned |

## Migration / Rollout

No data migration (greenfield). Bootstrap phase ships `pyproject.toml` + pytest (config `strict_tdd` → true) as PR #1. Chained PRs per proposal: ① bootstrap+tests → ② interpreter+orchestrator (fakes) → ③ executors+voice+E2E. Rollback: delete `jarvis/`, stop subprocesses, `git checkout` AGENTS.md (proposal rollback plan).

## Open Questions

- [ ] q5-medium gate: does quantized `ggml-medium-q5_0.bin` stay ≤4s on this CPU? (apply-time decision, recorded)
- [ ] Custom rioplatense wake-model training: does `jarvis.onnx` beat `hey_jarvis` base on the recorded corpus? (apply-time gate)
- [ ] Latency lever: add cheap regex fast-path for canonical non-destructive forms ("abrí X", "buscá X") to reach <3s objective for system/files/web? (post-PR-2 tuning)
- [ ] Interpreter LLM latency on first call (cold provider): spoken ack covers >3s; verify warm interpreter session stays 1-3s.

## Implementation Plan (for sdd-tasks)

1. **Bootstrap**: `jarvis/pyproject.toml`, package skeleton, `cli.py` start/stop/off/on stubs, `config.py` (spike paths), pytest bootstrap; signal: `pytest` green + `jarvis --help`.
2. **Interpreter core** (pure, no subprocesses): `normalize`, `golden`, `schema`, `llm` with injectable transport (fake provider in tests); corpus tests; signal: full unit suite green.
3. **Orchestrator core** (fake executors): `state`, `confirm` (injectable clock), `session`, `supervisor` policies; signal: FSM+confirm+re-ask tests green.
4. **Executors**: `system`, `files`, `web` (real, unit-tested with fakes), `opencode` server manager (fake server in tests, real `serve` in integration); signal: unit + integration smoke green.
5. **Voice**: `audio`, `wake` (openWakeWord), `stt`, `tts`; wake-model training gate + q5-medium gate (record decisions); signal: slow integration tests + decision records.
6. **E2E + polish**: `loop.py` wiring, demo `open repo → ask → shutdown`, latency report, `jarvis clean`, degrade path; signal: E2E demo + M1/M3 corpus replay pass.
