# Jarvis de Desarrollo

A fully local, Spanish-speaking voice assistant for everyday development work.
Jarvis listens for a wake word, transcribes offline with Whisper, resolves the
intent through a golden gate (plus an optional LLM), confirms destructive
actions verbally, and executes them against your repo — all without sending
audio or text to the cloud.

This MVP is defined by the SDD change **jarvis-mvp** (see `openspec/changes/`):
requirements, design and per-task evidence live there.

## Features

- **Voice loop**: wake word → offline Whisper STT → golden intent resolver →
  execution → piper TTS reply (`jarvis start`).
- **Four action domains** (registry in `jarvis/src/jarvis/actions/`):
  - opencode control — open repos in OpenCode with per-repo sessionIDs
  - system control — open allowed apps, run allowed commands
  - file management — create/edit allowed project files
  - web actions — open allowed URLs
- **Destructive action safety**: `cerrar linux`, `reiniciar la maquina`,
  `apagarse` and `cerrar` always require a spoken confirmation before running.
- **Local-by-default**: Spanish STT/TTS, openwakeword keyword, no cloud calls.
- **Degradation, not failure**: if OpenCode is unreachable Jarvis says so out
  loud and keeps the rest of the flow working.
- **Off switch without the mic (RF-11)**: `jarvis off` releases the mic and
  the loop ignores the wake word until `jarvis on` — a spoken wake word can
  never reactivate it because no mic is open.
- **Deletable local logs (RNF-3)**: transcripts and captured audio land under
  `~/.local/state/jarvis/logs/` and are removed with `jarvis clean` (state and
  config are preserved).

## Requirements

- Linux with a microphone
- Python 3.12+ and a virtualenv for the `jarvis` package
- Voice binaries under `spike/` (see `jarvis/src/jarvis/config.py` for exact
  paths): `whisper-cli` (whisper.cpp), `piper`, `openwakeword` models
  (`jarvis.onnx` custom keyword), `paplay` for playback
- OpenCode installed to open repos

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ./jarvis
```

Place the spike binaries/models as configured in `jarvis/src/jarvis/config.py`
(build them with the recipes in `spike/` if they are not already installed).

## Usage

```bash
jarvis start   # run the voice loop (announces readiness)
jarvis off     # release the mic; loop stops listening until `on`
jarvis on      # resume listening
jarvis clean   # delete local transcripts and audio logs (keeps state/config)
jarvis stop    # placeholder (future)
jarvis logs    # placeholder (future)
```

Voice commands (Spanish): e.g. "hola jarvis", "abrí firefox",
"creá un documento que diga…", "abrí este repositorio en opencode",
"abrí https://…", "cerrá la sesión", "apagate". While OFF the loop consumes no
mic input; `jarvis off`/`jarvis on` signal a running instance via
`~/.local/state/jarvis/jarvis.pid` (SIGUSR1/SIGUSR2).

## Configuration

All paths and behavior are constants in `jarvis/src/jarvis/config.py`:

- allowlists for apps, commands, files and URLs (execution gates)
- audio/VAD/STT/TTS/wake parameters
- model and binary paths under `spike/`
- session state: `~/.local/share/jarvis/state.json` (active project, repo
  sessionIDs, off switch)

## Tests

```bash
.venv/bin/pytest jarvis/tests -q                 # unit suite (no hardware)
.venv/bin/pytest jarvis/tests/e2e -m e2e         # e2e against real spike binaries
```

The unit suite covers the orchestrator FSM, confirmation flow, session
persistence, the golden gate, every action executor, the CLI, and the PRD
metrics (M4/M5/M6). E2E requires the real mic + spike binaries.

## Architecture

```
spike/                 whisper.cpp / piper / openwakeword recipes & binaries
jarvis/src/jarvis/
  config.py            paths, allowlists, model settings
  cli.py               jarvis start/off/on/clean entry point
  audio/               wake, capture+VAD, whisper STT, piper TTS, pipeline
  interpreter/         golden gate + optional LLM resolution → Intent
  orchestrator/        FSM loop, session state, confirmation, action registry
    logs.py            transcript journal + clean_logs (RNF-3)
    loop.py            run loop, start/off/on/clean, signal-based switch
  actions/             opencode / system / files / web executors
tests/                 unit + e2e (evidence per task in openspec/changes/)
```

## Status

- **Done**: voice loop, all four action domains, golden gate + LLM, verbal
  confirmation for destructive actions, off/on switch incl. non-vocal
  reactivation, local log cleanup, PRD metrics M4/M5/M6 verified, docs.
- **E2E / next improvements**: tuning the whisper small model for the target
  mic, training a `jarvis.onnx` custom keyword (currently using a generic
  openwakeword model), and a live demo over the real mic.
