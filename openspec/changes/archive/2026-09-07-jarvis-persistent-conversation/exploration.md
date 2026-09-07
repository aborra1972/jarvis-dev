# Exploration: Persistent conversation

## Status and authority

Exploration complete; proposal interview required. This is a new, user-approved planning change, not implementation approval. No proposal, source edits, tests, shell commands, hardware probes, child agents, or attempt ledger were produced. Existing staged changes were left untouched; `.env` was not read.

- Workspace: `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`.
- Canonical session: interactive, artifact store **both**, ask-on-risk, 800-line review budget, strict TDD.
- Parent-reported native preflight: `gentle-ai.sdd-status`, schemaVersion 2, artifactStore **openspec**, changeName/changeRoot null, zero active changes, no artifacts, dependencies blocked solely by no active change, nextRecommended `sdd-new`. Preserve the **both versus openspec mismatch**; neither constitutes implementation readiness.
- Planning home is repo-local `openspec`; allowed edit root is this repository. This phase writes only this exploration file and its explicitly requested Engram counterpart.
- `openspec/config.yaml` confirms session both and English artifacts, but its “no application code yet” context is stale relative to inspected sources. Config names Engram bucket `ale`; this delegation explicitly selects project `jarvis` for the exploration save.
- No upstream artifact is required. Archived `2026-08-15-jarvis-mvp` is historical, not resumed. `jarvis-voice-turn-taking-investigation` is parent-provided reference only; no Engram read tool was available to retrieve it, and no research selection or runtime research evidence grant is claimed.
- Instructions: injected Gentle AI skill read; root and immediate-parent AGENTS.md absent and repository AGENTS.md search returned none. Assigned role recovered at `/home/ale/.pi/agent/agents/sdd-explore.md` after no separate phase SKILL.md was found. `skill_resolution: fallback-path`; parent should inject the indexed phase path next time. No registry was read. No codegraph query was made because its workspace is `/home/ale`.

## Confirmed product goals

1. After activation, wait without a speech-start deadline.
2. Keep the conversation open across long pauses until explicit goodbye.
3. Let the user speak over TTS, stopping it and preserving the user's speech without self-trigger or echo.

The user selected sequential small slices. **Bounded, fail-closed safety confirmations are a parent-proposed exception requiring explicit confirmation during the proposal interview.** Unlimited idle waiting does not imply unlimited recordings, indefinite destructive authorization, or persistence of listening across restarts.

## Verified current behavior

Evidence paths below are repository-relative; statements describe inspected source, not measured runtime behavior.

| Evidence | Finding and consequence |
| --- | --- |
| `jarvis/src/jarvis/audio/capture.py`, `gather_utterance` | Every frame immediately counts toward silence and duration; approximately 800 ms of initial silence ends capture without waiting for first speech. A missing frame (`None`) also ends capture. Cancellation callback is already polled before reads. |
| `jarvis/src/jarvis/config.py:118-143`; `orchestrator/loop.py`, `build_pipeline` | Default wake engine is `name`, silence is configured separately, runtime utterance maximum is 120 s, follow-up window is 8 s, barge-in is disabled. Low-level capture defaults remain 10 s; changing only that constant would miss runtime wiring. |
| `audio/pipeline.py`, `UtteranceCapture.capture` | Resets VAD, gathers and then synchronously transcribes; temporary WAV is removed afterward and last audio remains in memory for speaker verification. Silence gate also uses RMS. |
| `audio/pipeline.py`, `PiperSpeaker` | `speak` queues asynchronously. `is_playing` includes queued/in-flight work. `flush(timeout=10)` can return with work still outstanding and gives no completion outcome. `interrupt` only calls playback stop; it neither invalidates queued text nor cancels synthesis. |
| `audio/playback.py`, `Playback` | WAV uses `paplay`; MP3 uses `gst-launch-1.0 playbin`. A subprocess handle can be terminated. There is no echo-reference routing or AEC processing in this adapter. Beeps share the same playback object. |
| `orchestrator/loop.py`, `_tick` LISTENING | Capture includes STT before the loop stops the mic; contrary to an overbroad scout summary, it is not stopped for the entire recognition interval. It is stopped after transcript/name/speaker checks, before interpretation. Re-ask queues TTS and immediately returns to LISTENING with no explicit playback wait or mic reopen. |
| `orchestrator/loop.py`, EXECUTING/IDLE/SPEAKING | Successful execution starts the follow-up deadline when a reply may still be queued/playing. IDLE observes playback end and applies a 2 s cooldown. The follow-up allowance is consumed on entry, so silence drops back to wake-gated idle; a long reply can consume the whole window. Follow-up beeps occur after mic restart, with no matching mic-stop guard. |
| `orchestrator/loop.py`, IDLE barge-in | Optional legacy path raises the wake threshold during playback but explicitly excludes the default name-gated engine. Name wake keeps the mic stopped. A higher threshold is not echo cancellation. Blocking execution/stream generation also prevents relying on IDLE as a universally available interruption monitor. |
| `orchestrator/confirm.py`, `confirm` | Confirmation queues its prompt, starts a nominal 15 s deadline and a 3x hard deadline, then calls capture. Neither deadline can interrupt blocking capture; verdict classification happens before expiry checks, potentially accepting a late affirmative. Loop CaptureError retries call confirm again, restarting the deadline. There is no explicit prompt-completion wait/mic reopen here. |
| `interpreter/schema.py`; `interpreter/golden.py` | Allowlist has `power_off_self`, not a distinct end-conversation intent. Power-off is destructive and separately confirmed. Goodbye must not accidentally become shutdown or process exit. |
| `orchestrator/session.py`, `record_turn`; `tests/unit/test_session.py` | Conversation history already has immediate persistence and reload coverage. Open listening-session state is a separate concern from persisted conversational history. |

Baseline `openspec/specs/voice-pipeline/spec.md` requires wake gating and dropping all audio during TTS. True barge-in necessarily needs an explicit specification delta preserving the no-self-trigger outcome rather than the blanket discard mechanism. `openspec/specs/assistant-lifecycle/spec.md` requires off to release audio and reactivation to be non-vocal; conversation close must not silently redefine off. README privacy claims coexist with Edge TTS and Gemini options in runtime wiring, so extended listening cannot be represented as unconditionally local-only processing.

## Approaches and recommendation

**Do not simply increase timeouts or enable the existing barge-in flag.** Larger timeouts retain initial-silence termination and consume more confirmation/recording time; the flag does not serve the default wake engine or establish echo safety.

Prefer explicit capture modes and a lightweight conversation lifecycle, followed by a separately gated audio-interruption slice. Reuse existing injected capture, speaker, clock, and executor seams. Avoid a wholesale audio-backend replacement unless later hardware evidence requires it.

### Slice 1 — Cancellable indefinite waiting, bounded utterances

Separate waiting for first speech from collecting an utterance. Indefinite idle should discard silence or retain only bounded pre-roll, not accumulate an endless WAV/list. Start utterance duration/trailing-silence limits after speech begins. Distinguish transient no-frame reads from device failure; retain bounded polling and immediate off/cancel responsiveness. Explicit finite capture/deadline policy must remain available to confirmation callers before any default becomes indefinite.

Minimal likely sources: `audio/capture.py`, `audio/pipeline.py`, `orchestrator/loop.py`; `orchestrator/confirm.py` and contracts only as needed for deadline propagation. Tests: `test_audio_capture.py`, `test_audio_pipeline.py`, `test_confirm.py`, `test_switch_signal.py`. Future RED cases: arbitrarily long initial silence followed by speech; bounded pre-roll/memory; missing frames; cancel/off during waiting; retained utterance cap; expired affirmative rejected; prompt failure and capture failure remain bounded. No test execution occurred here.

### Slice 2 — Open conversation with explicit closure

Replace the one-shot follow-up deadline with explicit active/inactive conversational state. Apply it consistently after replies, silence, re-asks, and recoverable errors; coordinate prompt completion and mic reopening without fixed sleeps as correctness guarantees. Choose a deterministic session-ending intent/control distinct from process power-off, and resolve its precedence relative to dictation and confirmation. Preserve authorization gates and history semantics.

Minimal likely sources: `orchestrator/loop.py`, `interpreter/schema.py`, `interpreter/golden.py` or a narrowly scoped control parser; `orchestrator/state.py`, `contracts.py`, configuration and lifecycle handler only if the chosen design requires them. Tests: `test_loop.py`, `test_name_gate.py`, `test_golden.py`, `test_confirm.py`; retain `test_session.py` regression coverage. Future cases: long pause before first/follow-up speech; long TTS exceeding former window; re-ask mic readiness; exact goodbye versus quoted/negated goodbye; goodbye during pending confirmation; off/restart; dictation precedence. Do not expand this slice into a history-storage rewrite.

### Slice 3 — Evidence-gated speech interruption

First define interruption ownership across synthesis, queued utterances, active playback, streamed producers, capture pre-roll, and post-stop residual echo. Cancellation needs a generation/token or equivalent invalidation so stopped responses cannot resume from queued or newly streamed sentences. Interrupting audio must not imply cancelling or rolling back an already executed command. A shared playback process slot and concurrent beep/TTS calls need serialization or explicit ownership.

Minimal likely sources: `audio/pipeline.py`, `audio/playback.py`, `orchestrator/loop.py`, `audio/capture.py` and `contracts.py`; wake/stream producer integration only where required. Tests: `test_audio_pipeline.py`, `test_audio_playback.py`, `test_loop.py`, `test_audio_capture.py`, with controlled fake synthesis/player races. Future cases: interrupt during synthesis/playback/queued sentences; no stale response restart; first user syllables preserved; off wins; playback-only audio never dispatches a command.

**Hardware feasibility remains unverified.** The source supports stopping a player subprocess, not reliably distinguishing user speech from loudspeaker leakage. Silero speech detection and post-capture speaker verification are not AEC. The intended microphone, speaker/headset, server routing, latency, and any pre-existing echo-cancel source must be established with separately authorized evidence later. Headset isolation, a verified system echo-cancel source, or an application reference/capture redesign are alternatives, not approved decisions. Wake-only interruption is a limited fallback, not fulfillment of arbitrary speak-over-TTS. Do not promise speakerphone AEC or declare this slice ready from unit tests alone.

Each slice should receive its own strict-TDD implementation plan and review boundary below the 800-line session budget; file lists are impact estimates, not permission to edit. Keep a reversible path to finite/wake-gated behavior and leave interruption disabled until its acceptance gate passes. Re-budget before an audio-backend redesign.

## Risks and proposal-interview questions

1. **Safety exception:** Confirm that destructive/risky action confirmations stay finite and fail closed while ordinary conversation waits indefinitely. Retain 15 s or choose another duration? When does the response window start relative to verified prompt completion, and should any technical retry consume the same overall authorization deadline? Late yes, goodbye, off, echo, or unrelated speech must not authorize stale work.
2. **Goodbye contract:** Which exact Spanish phrases end conversation? Return to wake standby, stop recording entirely, or exit? Is acknowledgement wanted? How should quoted/negated goodbye and ambiguous “pará/cancelá” behave? Distinguish speech-stop, action cancel, conversation close, and power-off.
3. **Activation and persistence:** Does conversation open immediately after wake even before a valid command, and remain open after rejection/STT failure? Should off/on, agent switch, restart, or device loss always require fresh activation? “Persistent” currently establishes long pauses, not automatic listening after restart or new history retention requirements.
4. **Interruption UX and hardware:** Must any speech interrupt, or is addressing the assistant acceptable as an interim mode? Which actual mic/output/audio-server arrangement must work? What stop latency, first-syllable retention, and acceptable false-interruption/self-trigger criteria should be verified? If speakers cannot be made echo-safe, is a headset requirement or explicit non-vocal fallback acceptable?
5. **Privacy and bystanders:** Should open conversation process any nearby speaker or only an enrolled speaker? What visible listening indicator and mute control are required? Are existing transcript/history retention and configured cloud text/TTS services acceptable during extended sessions? Long idle must not create retained recordings of silence/background conversation by default.
6. **Turn boundaries and competing modes:** Keep the current 800 ms trailing pause and 120 s spoken-utterance cap? How should a long pause mid-thought behave? During dictation or an executing command, should new speech become a follow-up, replace a pending request, merely stop audio, or be deferred? What happens to interrupted answer history and queued reminders?

## Handoff

Recommended next action: **proposal interview (`sdd-propose` clarification), not proposal generation or apply yet**. Resolve the product questions, explicitly confirm the safety exception, and preserve backend mismatch in parent context. No research phase is selected. Future hardware validation requires separate authorization; unavailable runtime research evidence grants are not bypassed by this exploration.
