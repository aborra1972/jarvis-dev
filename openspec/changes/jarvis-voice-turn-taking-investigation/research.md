# Research: Jarvis Voice Turn-Taking Investigation

## Status

- Change: `jarvis-voice-turn-taking-investigation`
- Revision: 3
- Outcome: research completed enough for pre-proposal/product decisions
- Accessed at: 2026-09-07

## Questions

1. Identify the official ESCLabs product pages and linked source repositories for AI Chat Bot and DeskBuddy.
2. Determine the voice pipeline and turn-taking design of both projects.
3. Compare the evidence with local Jarvis.
4. Propose root causes and minimal adaptations, separating facts from inferences.

## Sources

### S1 — ESCLabs ESP32 AI Chatbot Kit product page

- URL: https://www.esclabs.in/product/esp32-ai-chatbot-kit/
- Class: official product page
- Evidence: The page describes an ESP32-based AI chatbot kit and links the video tutorial `https://youtu.be/B7jzMLpdjqo`. The kit contains Xiao ESP32-S3, 0.96 inch OLED, MAX98357 I2S amplifier, INMP441 microphone, battery, booster, push button, USB socket, and speaker.

### S2 — AI-CHAT-BOT GitHub repository

- URL: https://github.com/EDISON-SCIENCE-CORNER/AI-CHAT-BOT
- Class: official/linked source repository
- Evidence: The repository contains `Source.zip` plus firmware binaries. The downloaded `Source.zip` is 3,952,516 bytes and unpacks successfully.

### S3 — AI-CHAT-BOT Source.zip / xiaozhi-esp32-2.2.2

- URL: https://raw.githubusercontent.com/EDISON-SCIENCE-CORNER/AI-CHAT-BOT/main/Source.zip
- Class: source archive
- Evidence: The archive root is `Source/xiaozhi-esp32-2.2.2/`, containing `main/application.cc`, `main/audio/audio_service.*`, `main/audio/processors/afe_audio_processor.cc`, protocol code, board code, and docs. It appears to be an adapted Xiaozhi ESP32 firmware tree rather than a small bespoke sketch.

### S4 — ESCLabs DeskBuddy ESP32-C3 product page

- URL: https://www.esclabs.in/product/desk-buddy-pet-robot-esp32c3-mini-weather-station/
- Class: official product page
- Evidence: The page lists OLED emotional animations, Wi-Fi time/weather forecast, touch interaction, rechargeable design, and open-source hardware/software. It does not claim voice input, STT, TTS, wake word, or audio turn-taking.

### S5 — ESCLabs DeskBuddy 2.0 product page

- URL: https://www.esclabs.in/product/deskbuddy-2-0-kit/
- Class: official product page
- Evidence: The fetched page did not expose useful voice-pipeline details; it mainly returned related products/content. No voice turn-taking claim was validated from this page.

### S6 — DESKBUDDY-1.0 GitHub repository

- URL: https://github.com/EDISON-SCIENCE-CORNER/DESKBUDDY-1.0
- Class: official/linked source repository
- Evidence from prior research: `deskbuddy.ino` implements Wi-Fi, weather/time, OLED animations, and touch interaction. It does not implement capture, STT, TTS, wake word, or playback.

### L1 — Local Jarvis orchestrator loop

- Path: `jarvis/src/jarvis/orchestrator/loop.py`
- Evidence: The FSM explicitly controls `IDLE`, `LISTENING`, `CONFIRMING`, `EXECUTING`, `SPEAKING`, cooldown, wake flush, capturer flush, follow-up window, and optional barge-in.

### L2 — Local Jarvis capture

- Path: `jarvis/src/jarvis/audio/capture.py`
- Evidence: `gather_utterance()` appends every block, increments `silent_s` from the beginning, and stops after trailing silence even before first speech. There is no separate start-of-speech timeout.

### L3 — Local Jarvis audio pipeline

- Path: `jarvis/src/jarvis/audio/pipeline.py`
- Evidence: `PiperSpeaker.speak()` enqueues and returns immediately. `is_playing()` reports queued/active playback. `interrupt()` stops the current playback backend but does not drain pending TTS queue entries.

### L4 — Local Jarvis confirmation gate

- Path: `jarvis/src/jarvis/orchestrator/confirm.py`
- Evidence: `confirm()` calls `speaker.speak(confirmation_prompt(intent))` and then immediately enters `capture()` without a playback-finished/listen barrier.

## Validated claims

1. AI Chat Bot is the relevant ESCLabs voice project. Its official product page describes a Xiao ESP32-S3 + OLED + I2S speaker/mic chatbot kit and links a tutorial.
2. AI Chat Bot's `Source.zip` is inspectable now. It contains `xiaozhi-esp32-2.2.2`, a Xiaozhi ESP32 firmware tree with a stateful audio protocol, Opus transport, AFE/VAD/AEC support, wake word support, and explicit listening/speaking states.
3. DeskBuddy is not a useful voice turn-taking reference. The official product page and visible firmware evidence show display/weather/touch behavior, not a voice assistant pipeline.
4. Xiaozhi's turn-taking model is streaming/stateful: mic audio is encoded to Opus and sent over WebSocket/MQTT; server audio is decoded to playback; JSON messages signal `listen/start`, `listen/stop`, `abort`, and server `tts/start`/`tts/stop`.
5. Xiaozhi separates listening modes: `auto`, `manual`, and `realtime`. Realtime mode is tied to AEC; when not realtime, entering speaking disables voice processing and only AFE wake word may remain enabled.
6. Xiaozhi waits for the playback queue to empty before enabling auto-stop listening. The code comment says this prevents audio truncation when `STOP` arrives late due to network jitter.
7. Jarvis already contains several comparable protections: stopping mic during speech, cooldown after actual playback end, wake/capturer flush, follow-up window, optional barge-in, and fast mic close after user speech.
8. Jarvis still has weaker turn-boundary guarantees in two places: capture start does not distinguish initial silence from trailing silence, and confirmation/reask can enqueue TTS then immediately capture without a general `speak-and-then-listen` barrier.

## Comparison: Xiaozhi/AI Chat Bot vs Jarvis

| Concern | Xiaozhi / AI Chat Bot evidence | Local Jarvis evidence | Implication |
| --- | --- | --- | --- |
| Pipeline shape | Streaming Opus mic/server audio with protocol-level listen/tts/abort messages | Local capture → WAV/STT → interpret/execute → async TTS/playback | Jarvis has simpler batch turns; bugs are likely local timing/buffer issues, not protocol negotiation. |
| Turn state authority | Device state + server events (`tts/start`, `tts/stop`, `listen/start`, `listen/stop`) | Python FSM + `speaker.is_playing()` + local time/cooldown | Jarvis needs strong local barriers because there is no server event authority. |
| AEC/VAD | ESP AFE VAD/AEC; realtime mode requires AEC | Silero or energy VAD; no real AEC | Keeping mic closed during playback remains the right default. |
| Follow-up | Auto/realtime listening modes managed through protocol | Follow-up window starts after execution, then later IDLE listens once | Follow-up should be anchored to actual playback end, not command execution completion. Current code already waits until not playing before entering follow-up, but the deadline is computed earlier and can expire during long TTS. |
| Confirmation | Protocol sends explicit listen control | `confirm()` speaks prompt and captures immediately | Highest-confidence local defect candidate. |
| Barge-in | Wake during speaking sends abort with wake-word reason | Optional; stops current playback only | If enabled, Jarvis should also clear queued TTS/generation state. |

## Root-cause hypotheses for Jarvis

### H1 — Initial silence is treated as trailing silence

- Evidence: `gather_utterance()` increments `silent_s` immediately, before speech has started.
- User-visible failure: after wake/beep, Jarvis may stop listening after ~800 ms of initial silence and return `silence` before the user begins speaking.
- Confidence: high from static code.
- Minimal adaptation: split capture into `waiting_for_speech` and `in_speech`; use a start-of-speech timeout plus trailing-silence timeout.

### H2 — Confirmation/reask lacks a playback-finished listening barrier

- Evidence: `confirm()` enqueues the prompt with `speaker.speak()` then immediately calls `capture()`; reask paths return `State.LISTENING` immediately after `speaker.speak()`.
- User-visible failure: Jarvis may capture its own prompt, clip the user, or time out while it is still speaking.
- Confidence: high for confirmation; medium for reask because the main loop's `IDLE` speaking gate does not apply when returning directly to `LISTENING`.
- Minimal adaptation: introduce `speaker.speak_and_wait(text)` or a helper `speak_then_listen()` that waits for playback completion, applies cooldown/flush, then starts capture.

### H3 — Follow-up deadline can expire while Jarvis is still speaking

- Evidence: `conversation_until` is set after execution, before TTS playback completes. IDLE does not consume the follow-up until `speaker.is_playing()` becomes false.
- User-visible failure: long spoken replies can consume most/all of the follow-up window.
- Confidence: medium/high.
- Minimal adaptation: set `conversation_until` after actual playback end, or store a `pending_follow_up` flag and compute the deadline when playback transitions from playing to finished.

### H4 — Barge-in only stops active playback

- Evidence: `PiperSpeaker.interrupt()` calls playback `stop()` only; it does not drain `_queue`.
- User-visible failure: interrupted output can resume with queued stale speech.
- Confidence: medium; only applies when `BARGE_IN_ENABLED` is true.
- Minimal adaptation: add a queue-drain/cancel method and call it on barge-in.

### H5 — DeskBuddy should be removed as a voice reference

- Evidence: official page/repo evidence does not show any voice pipeline.
- User-visible failure: wasting design effort comparing against a non-voice project.
- Confidence: high.
- Minimal adaptation: keep DeskBuddy only as display/personality inspiration, not audio turn-taking evidence.

## Candidate experiments before implementation

1. Instrument event timestamps: `wake_fired`, `beep_start/end`, `capture_start`, `first_speech`, `speech_end`, `tts_enqueue`, `tts_start`, `tts_end`, `mic_start/stop`, `flush_start/end`.
2. Add tests for `gather_utterance()` with initial silence followed by speech: it must not stop before speech until a separate start timeout fires.
3. Add confirmation test: `confirm()` must not call capture before the prompt playback has completed and buffers have been flushed.
4. Add reask test: after unclear input, Jarvis should speak the reask prompt fully before listening again.
5. Add follow-up test with long TTS: follow-up window should begin after playback end.
6. Add barge-in test: interrupt clears active playback plus pending queue.

## Recommended minimal implementation order

1. Fix capture phase boundaries: start-of-speech timeout vs trailing silence.
2. Add a reusable `speak_then_listen` barrier and route confirmation/reask through it.
3. Re-anchor conversation follow-up deadline to actual playback completion.
4. If barge-in remains enabled, clear pending TTS on interrupt.
5. Keep DeskBuddy out of the voice turn-taking design except as non-audio UI inspiration.

## Additional research pass: external issue evidence

The follow-up research pass checked Xiaozhi issue/PR evidence around playback/listening races and abort behavior.

### E1 — Xiaozhi playback-tail race

- Sources: `78/xiaozhi-esp32` issues/PRs around auto-stop listening and playback queue draining, especially PR #1675 and related issue references.
- Evidence summary: TTS tail truncation was attributed to a race among `tts.stop`, network jitter, and local decoder/playback queues. A fixed server delay was treated as a workaround; the client-side correction waits for playback/decode queues to drain before enabling voice processing and listening again.
- Local implication: Jarvis should not rely only on fixed sleeps. Its already-added `is_playing()` gate is directionally correct, but confirmation/reask paths bypass that IDLE gate by entering capture directly.

### E2 — Xiaozhi abort-state failures

- Sources: `78/xiaozhi-esp32` and `xiaozhi-esp32-server` issues around `abort`, wake-during-speaking, and stuck speaking/unresponsive WebSocket reports.
- Evidence summary: abort is not just playback stop; delayed server/LLM/ASR processing may restart speech unless the whole processing path is cancelled. Some reports are version/hardware dependent, but they validate the design risk.
- Local implication: Jarvis barge-in should cancel active playback plus pending queued utterances; if future generation streams into TTS, cancellation must cover that producer too.

## Additional research pass: local test coverage gaps

Local tests already cover many safety rails, but they do not prove the suspected turn-taking boundaries:

- `jarvis/tests/unit/test_audio_capture.py` covers trailing silence and max duration, but has no failing test for initial silence followed by speech. Current `gather_utterance()` would stop after the silence window before speech begins.
- `jarvis/tests/unit/test_confirm.py` verifies yes/no/timeout classification, but its fake speaker is synchronous and cannot catch `speaker.speak()` immediately followed by `capture()`.
- `jarvis/tests/unit/test_loop.py` verifies cooldown starts after playback finishes and verifies conversation follow-up skips the name gate, but it does not prove the follow-up window is created after playback end rather than after execution.
- `jarvis/tests/unit/test_audio_pipeline.py` verifies `PiperSpeaker.is_playing()` and async queue behavior, but no test currently requires `interrupt()` to clear queued speech.

## Proposal readiness

Research blockers from revision 2 are resolved:

- Official ESCLabs product pages were fetched.
- `AI-CHAT-BOT Source.zip` was downloaded and inspected read-only under `/tmp/jarvis-ai-chatbot-research`.

The user selected `Investigar más`, so proposal remains intentionally paused.

Remaining useful pre-proposal evidence:

1. Run or add RED tests for the four suspected local timing defects before any implementation.
2. Optionally run one manual audio reproduction session with timestamp logging enabled.
3. After evidence, confirm first-slice scope and proceed to proposal.
