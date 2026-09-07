# Sync Report: jarvis-persistent-conversation

## Status

**synced** — verified first slice only.

Canonical OpenSpec was updated from the passing verification boundary for PC-V04 and PC-S01. The change remains active and was not archived.

## Domains synced

- `voice-pipeline`: added PC-V04 speech-onset waiting, bounded idle retention, finite post-onset capture, cancellation, and device-failure semantics.
- `system-control`: modified the existing shutdown/reboot confirmation requirement with PC-S01 prompt-completion deadlines, fail-closed authorization, stale-result rejection, final execution checks, and non-renewable retries.

No assistant-lifecycle or command-interpreter delta was merged because persistent conversation, goodbye control, and related lifecycle/parser behavior are outside this verified first slice.

## Canonical files updated

- `openspec/specs/voice-pipeline/spec.md`
- `openspec/specs/system-control/spec.md`

## Requirement changes

- ADDED: `Separate speech-onset waiting from utterance endpoint (PC-V04)`.
- MODIFIED: `Shutdown/reboot verbal confirmation (RF-5, RF-8, M6)` with PC-S01 semantics.
- REMOVED: none.
- RENAMED: none.

## Boundary and exclusions

This sync reflects PR1–PR3 verification and does not claim PC-V06. Persistent conversation (PC-L02), goodbye parser/control (PC-C01), barge-in/AEC, queued or in-flight TTS cancellation, hardware acceptance, provider or retention changes, history redesign, new commands, speaker enrollment, and backend rewrite remain out of scope. No hardware evidence exists or is claimed. The existing non-overlapping/no-self-trigger behavior remains authoritative until the separate hardware gate is met.

## Verification evidence

- Full suite: `jarvis/.venv/bin/pytest -q` — **912 passed**, exit 0; one pre-existing unknown `e2e` mark warning.
- Focused PR3 tests: **7 passed**, exit 0.
- Adjacent audio/orchestrator tests: **96 passed**, exit 0.
- `git diff --check` — exit 0.
- Verification report: `verdict: pass`, `blockers: 0`, `critical_findings: 0`, `requirements: 4/4`, `scenarios: 20/20`.

## Guardrails and collisions

- Active same-domain collision: none found.
- Legacy flat change spec: none; domain specs are present.
- Destructive sync: no REMOVED requirements and no destructive approval required. The PC-S01 MODIFIED requirement is a focused first-slice replacement, not a large unrelated delta.
- No `RENAMED Requirements` delta was synced.
- Application source, tests, `TAREAS.md`, proposal, design, and tasks were not edited by this phase.

## Structured status and action context

```yaml
schemaName: spec-driven
changeName: jarvis-persistent-conversation
artifactStore: both
changeRoot: /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev/openspec/changes/jarvis-persistent-conversation
artifacts: {proposal: done, specs: done, design: done, tasks: done, applyProgress: done, verifyReport: pass, syncReport: done}
taskProgress: {total: 22, complete: 22, remaining: 0, unchecked: []}
actionContext:
  mode: repo-local
  workspaceRoot: /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev
  allowedEditRoots:
    - /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev/openspec/specs/voice-pipeline/spec.md
    - /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev/openspec/specs/assistant-lifecycle/spec.md
    - /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev/openspec/specs/system-control/spec.md
    - /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev/openspec/specs/command-interpreter/spec.md
    - /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev/openspec/changes/jarvis-persistent-conversation/sync-report.md
  warnings: []
nextRecommended: sdd-archive
isNonAuthoritative: false
```

## Remaining archive prerequisites

The change folder must remain active until the archive phase runs. Archive readiness now requires review of this sync report, confirmation that the canonical first-slice merge is acceptable, and the normal archive operation. No hardware acceptance is required for this first-slice sync, but PC-V06 must remain disabled and unclaimed.

## Key Learnings

1. Canonical sync must follow the verified requirement boundary rather than merge every planned delta.
2. Unit evidence for capture and confirmation does not establish the separate dual-target hardware interruption gate.
3. A passing full regression can coexist with persistent-conversation and goodbye work remaining explicitly unsynced.
