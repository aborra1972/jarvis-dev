# Change Spec: jarvis-mvp — Local Voice Assistant MVP

## Summary

Adds the complete voice→action bridge as 7 NEW capabilities (15 commands in 5 domains, 5 runtime components per RNF-5). No existing specs to modify (`openspec/specs` was empty). Each capability is specified as a full spec under `openspec/specs/` and will be merged into main specs at archive time.

## Capabilities Added

| Capability | Spec | Coverage |
|------------|------|----------|
| voice-pipeline | `openspec/specs/voice-pipeline/spec.md` | Wake word (openWakeWord, RF-1); local STT whisper small es/beam1/VAD/prompt (RNF-2, M3); piper es_AR-daniela TTS (RF-4); latency <6s / <3s objective (RNF-1, M2); no self-trigger |
| command-interpreter | `openspec/specs/command-interpreter/spec.md` | LLM-first intent resolution (RF-2/RF-3); golden rule table as hard gate for shutdown/reboot/power_off_self; allowlist of 15 commands, no shell; re-ask ≤2× + transcript reveal (RNF-4) |
| opencode-control | `openspec/specs/opencode-control/spec.md` | Persistent headless serve/attach + sessionID (RNF-1); 6 commands (RF-3); active project detect/switch (RF-6); offline degrade (M4) |
| system-control | `openspec/specs/system-control/spec.md` | shutdown/reboot verbal confirm 15s / abort (RF-5, RF-8, M6); open_app allowlist; no arbitrary shell |
| file-management | `openspec/specs/file-management/spec.md` | create_doc new-only, never overwrite/edit/delete (RF-9); open_file_dir |
| web-actions | `openspec/specs/web-actions/spec.md` | web_search → browser direct; open_url validated (RF-10) |
| assistant-lifecycle | `openspec/specs/assistant-lifecycle/spec.md` | Manual `jarvis start` (MVP); power_off_self; help; switch on/off, reactivation non-vocal only (RF-11); deletable local logs (RNF-3) |

## Traceability

- **RF-1** → voice-pipeline (wake word)
- **RF-2, RF-3** → command-interpreter, opencode-control
- **RF-4** → voice-pipeline (dual feedback)
- **RF-5, RF-8** → system-control (confirm gate, open_app)
- **RF-6** → opencode-control (active project)
- **RF-9** → file-management
- **RF-10** → web-actions
- **RF-11** → assistant-lifecycle (switch, logs)
- **RNF-1 / M2** → voice-pipeline (latency), opencode-control (persistent server)
- **RNF-2 / M3** → voice-pipeline (STT accuracy)
- **RNF-3** → assistant-lifecycle (local logs)
- **RNF-4** → command-interpreter (re-ask/reveal)
- **RNF-5** → all (5 runtime components)
- **M4** → opencode-control, system-control (degrade, no regression)
- **M6** → system-control (100% confirmations)
- **M5** → opencode-control + system-control + file-management + web-actions (4 domains)

## Out of Scope (not specified)

logout, WSL2, auto-start, file edit/delete, arbitrary shell, LLM-only interpreter, cloud processing (RNF-3 opt-in post-MVP).
