```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:9906c248fb0749fb5ee29534deb37bfd0b751e9552d377c98614df90
verdict: fail
blockers: 2
critical_findings: 2
requirements: 1/8
scenarios: 2/19
test_command: cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_loop.py jarvis/tests/unit/test_spotify_service.py jarvis/tests/unit/test_spotify_local.py
test_exit_code: 0
test_output_hash: sha256:de83fa60872950d29ce8ec6b348f415bf96a2fc6cbef7a2e1aaad0f59f5db4c8
build_command: ""
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# SDD Verification — Uncommitted Stage 1 Spotify lifecycle candidate

## Verdict

**FAIL for archive/readiness; lifecycle cancellation corrections independently pass.** No source or test files were edited. Only this OpenSpec report is updated.

## Scope and coverage

Verified the uncommitted candidate in `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`, including the prior blocked-probe correction and the Popen/external-off correction. The directly verified requirement is `Spotify operations MUST preserve existing safety and lifecycle gates` (1/8 requirements; 2/19 scenarios). Stage 2, diagnostics, and unimplemented release acceptance are not claimed.

## Deterministic evidence

- **Popen cancellation after spawn: PASS.** An isolated fake executable recorded `playerctl -l` and `--player=spotify play`; cancellation after the control child PID appeared returned `cancelled` in 0.002s, recorded no `SIDE_EFFECT`, and issued no status command.
- **Bounded escalation: PASS.** An isolated process double that ignored `terminate()` was escalated to `kill()` within the bounded wait path.
- **External off while blocked: PASS.** A real `SIGUSR1` delivered while the control child was blocked cancelled the active operation with reason `switch_off`; the adapter returned `cancelled`, with no side-effect marker and no status invocation.
- **Lifecycle suppression: PASS.** The loop checks freshness before Spotify transcript/history recording, session turn recording, and speech; stale/off results are suppressed.
- **Safety/regressions: PASS.** Fixed argv, `shell=False`, bounded timeout, exact single Spotify identity, off precedence, epoch replacement, readiness barrier, confirmation, `power_off_self`, `open_app`, generic executor isolation, and non-Spotify paths are covered by the focused/full green suites.

## Test and validation commands

Focused:

```text
cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_loop.py jarvis/tests/unit/test_spotify_service.py jarvis/tests/unit/test_spotify_local.py
```

Result: exit 0; `60 passed in 19.45s`; output hash `sha256:de83fa60872950d29ce8ec6b348f415bf96a2fc6cbef7a2e1aaad0f59f5db4c8`.

Full:

```text
cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q
```

Result: exit 0; `1053 passed, 1 warning in 49.83s`; output hash `sha256:9d01c757eefb065e9bab9aee0dd3b70a96168fe9b50e18e3e65df21d9bc7ed5b`. The warning is the existing unknown `e2e` mark at `jarvis/tests/e2e/test_e2e_smoke.py:30`.

Build: no build command configured.

## Task completion and blockers

The lifecycle task 1.3.1 is checked. The following unchecked implementation tasks are CRITICAL completeness/archive blockers:

- [ ] Extend `jarvis/src/jarvis/diagnose.py` with safe local Spotify capability diagnostics and document Stage 1 commands/boundaries in `jarvis/docs/comandos_jarvis.md` (or the repository's selected command guide); add tests in `jarvis/tests/unit/test_diagnose.py` asserting no raw output or arguments leak. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED asserts missing/ambiguous capability and redaction failures; GREEN emits normalized actionable status; TRIANGULATE checks fake diagnostics plus an opt-in host probe; REFACTOR keeps existing diagnostics and `open_app` semantics unchanged. <!-- sdd-owner: implementation -->
- [ ] Run a Stage 1 acceptance pass with no network and no Spotify credentials, including deterministic unit tests and optional Linux-marked playerctl/MPRIS tests; record the exact command `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q`, the capability-spike result, and rollback boundary (unregister Spotify intents/service while retaining `open_app`). RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is the offline/no-credentials acceptance baseline before implementation; GREEN is the passing Stage 1 suite; TRIANGULATE is host probe plus regression suite; REFACTOR is the reviewed independent Stage 1 release slice. <!-- sdd-owner: implementation -->

All Stage 2 implementation rows are also unchecked and remain outside this Stage 1 candidate; therefore the change is not archive-ready.

## Strict TDD and workload

`apply-progress.md` contains RED → GREEN → TRIANGULATE → REFACTOR evidence for the correction. The focused tests are present and green, and the full suite is green. The candidate source/test slice remains within the declared Stage 1 review boundary; no chained-PR boundary was broadened and no size exception was inferred.

## Exact blockers

1. **CRITICAL:** Two Stage 1 implementation-owned tasks remain unchecked: diagnostics/documentation and the formal acceptance pass.
2. **CRITICAL:** Stage 2 implementation-owned tasks remain unchecked, so whole-change archive readiness cannot be granted; they are outside this requested candidate scope.

## Standard phase envelope

status: blocked
executive_summary: Popen child termination, bounded escalation, external-off invalidation, side-effect/history/speech suppression, and focused/full pytest all pass; unchecked implementation tasks block archive/readiness.
artifacts: openspec/changes/jarvis-spotify-control/verify-report.md
next_recommended: sdd-apply
risks: Diagnostics and formal Stage 1 acceptance remain undone; Stage 2 remains intentionally unimplemented; full change cannot be archived.
skill_resolution: fallback-path

## Key Learnings

1. Real child-process evidence is needed to prove cancellation prevents a started control side effect.
2. Signal-side token cancellation lets external off invalidate blocked work before the next loop tick.
