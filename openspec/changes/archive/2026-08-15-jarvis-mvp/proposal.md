# Proposal: jarvis-mvp — Local Voice Assistant MVP

## Intent

Thin voice→action bridge (PRD Option A; spike validated): wake word → local STT → interpreter → executors → TTS. Hands-free rioplatense Spanish control of OpenCode + system/file/web at <6s (RNF-1), ≥90% STT (M3), local-first privacy (RNF-3).

## Scope

### In Scope

- 15 commands (v4), 5 domains: opencode (open_repo, ask, configure, create_artifact, implement, review); system (shutdown, reboot — confirm 15s/abort; power_off_self; open_app); files (create_doc, open_file_dir — new-only); web (web_search → browser direct; open_url); help.
- 5 components (RNF-5): audio+VAD, STT, interpreter, orchestrator, TTS.
- openWakeWord day 1 (overrides explore); manual start; re-ask ≤2× then reveal transcript (RNF-4); offline degrade (M4); TTS+text.
- Active project: git-cwd/last-repo + voice switch (RF-6); configure edits AGENTS.md; deletable logs (RF-11).
- pytest bootstrap first; strict_tdd → true with runner.

### Out of Scope

- logout, WSL2, auto-start, file edit/delete, shell, LLM-only interpreter.

## Capabilities

### New

- voice-pipeline: openWakeWord; whisper-cli small (es, beam1, VAD, prompt); piper es_AR-daniela.
- command-interpreter: LLM-first (free natural language via OpenCode config); golden rule-based table as safety/verification ONLY for critical/destructive intents (shutdown, reboot, power_off_self) — never misinterpreted; repregunta + reveal.
- opencode-control: persistent headless serve/attach (cold ~9s breaks RNF-1); active project.
- system-control: shutdown/reboot confirm (15s); open_app; allowlist, no shell.
- file-management: create_doc new-only.
- web-actions: search/url via xdg-open.
- assistant-lifecycle: power_off_self, help, switch (RF-11), log cleanup.

### Modified

None (empty openspec/specs).

## Approach

Orchestrator = state machine (idle/listening/confirming/executing/speaking), supervises warm subprocesses (timeouts/restart), drops audio while speaking; executors in actions/*.py. Interpreter is LLM-first (OpenCode provider) with a rule-based golden table as hard gate for destructive intents. Reuses spike artifacts; zero new native deps.

## Delivery Slicing (800-line budget; ask-on-risk)

Chained PRs: ① bootstrap+tests (pyproject, skeleton, interpreter tests) → ② interpreter+orchestrator (fakes) → ③ executors+voice+E2E (open repo → ask → shutdown). Forecast in sdd-tasks.

## Affected Areas

jarvis/pyproject.toml, jarvis/src/jarvis/**, jarvis/tests/** (all New).

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM commands 4–8s vs <3s (RNF-1) | High | persistent server, spoken ack |
| openWakeWord training | Med | base tune, fallback |
| STT rioplatense accuracy | Med | prompt bias, q5 gate, repregunta |
| serve instability | Med | health-check/restart; degrade (M4) |
| configure edits AGENTS.md | Low | target repo only; git rollback |

## Rollback Plan

Manual start ⇒ no installed services/OS changes. Revert: delete jarvis/ + pyproject, `git clean`; stop serve/subprocesses; AGENTS.md via `git checkout`.

## Dependencies

Spike whisper-cli + piper venv; opencode ≥1.18.18; openwakeword + trained model; pytest; sounddevice/arecord; xdg-open; logind+polkit.

## Success Criteria

- [ ] E2E demo: open repo → ask → shutdown (confirm)
- [ ] M1 ≥70% no-rewrite; M2 <6s; M3 WER ≥90%; M5 4 domains; M6 100%
- [ ] M4 degrade; q5-medium gate decision recorded
- [ ] strict_tdd true (runner present)
