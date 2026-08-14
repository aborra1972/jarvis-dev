# system-control Specification

## Purpose

Executes OS control actions (shutdown, reboot, open app) behind a strict safety gate: verbal confirmation with 15s timeout (RF-5/RF-8, M6), application allowlist, and no arbitrary shell (M4). Executor is an in-process module (RNF-5).

## Requirements

### Requirement: Shutdown/reboot verbal confirmation (RF-5, RF-8, M6)

Shutdown and reboot MUST require verbal confirmation with a 15s timeout. Explicit refusal or timeout MUST abort the action. 100% of destructive actions MUST be confirmed before execution (M6).

#### Scenario: Confirmed

- GIVEN the user says "Jarvis, cerrá Linux"
- WHEN the system asks "¿confirmás que apago la máquina?" and the user says "sí"
- THEN the system MUST shut down

#### Scenario: Refused

- GIVEN a confirmation prompt is open
- WHEN the user says "no"
- THEN the action MUST be aborted
- AND no shutdown/reboot MUST occur

#### Scenario: Timeout aborts

- GIVEN a confirmation prompt is open
- WHEN no response arrives within 15s
- THEN the action MUST be aborted (M6)
- AND the system MUST return to listening

### Requirement: Open application (RF-8)

The system MUST open applications via xdg-open from a predefined allowlist. Applications outside the allowlist MUST be rejected.

#### Scenario: Allowed app

- GIVEN the user says "Jarvis, abrí Firefox"
- WHEN executed
- THEN Firefox MUST open

#### Scenario: Disallowed app

- GIVEN the user requests an application not in the allowlist
- WHEN evaluated
- THEN the system MUST reject it with a spoken message
- AND MUST NOT attempt to run it

### Requirement: No arbitrary shell (M4)

System actions MUST be limited to the allowlisted actions. The system MUST NOT expose or execute arbitrary shell commands.

#### Scenario: Shell-like request

- GIVEN the user says "Jarvis, corré apt update"
- WHEN evaluated
- THEN the system MUST reject it as unsupported
- AND MUST NOT spawn any shell
