# opencode-control Specification

## Purpose

Controls OpenCode exclusively through a persistent headless server (serve/attach with sessionID) so cold-start latency (~9s) never violates RNF-1. Supports 6 commands (RF-3), manages the active project (RF-6), and degrades safely offline (M4). Executor is an in-process module (RNF-5).

## Requirements

### Requirement: Persistent headless server (RNF-1)

OpenCode commands MUST run against a persistent headless `serve` session with sessionID reuse via attach. A cold `run` per command MUST NOT be used.

#### Scenario: Ask uses existing session

- GIVEN a persistent server is running for the active project
- WHEN the user says "Jarvis, preguntale cómo funciona el middleware de auth"
- THEN the ask MUST execute on the existing session
- AND the response MUST arrive within the latency budget (RNF-1)

#### Scenario: Server recovery

- GIVEN the server is down or unhealthy
- WHEN an OpenCode command is issued
- THEN the orchestrator MUST health-check and restart it
- AND if recovery fails, the system MUST degrade to a spoken error (M4)

### Requirement: OpenCode command set (RF-3)

The system MUST support `open_repo`, `ask`, `configure`, `create_artifact`, `implement`, and `review`.

#### Scenario: open_repo

- GIVEN the user says "Jarvis, abrí OpenCode en el repo anubis-api"
- WHEN executed
- THEN a session for that repo MUST be attached
- AND that repo MUST become the active project

#### Scenario: configure

- GIVEN the user says "Jarvis, setéalo en modo SDD con artifacts en engram"
- WHEN executed
- THEN the AGENTS.md of the ACTIVE project MUST be updated (target repo only)

#### Scenario: implement without active project

- GIVEN no active project is selected
- WHEN the user says "Jarvis, pedile que implemente la migración 076 con TDD"
- THEN the system MUST NOT run the agent
- AND it MUST ask the user to select a project

#### Scenario: create_artifact

- GIVEN the user says "Jarvis, ayudame a armar un PRD para..."
- WHEN executed
- THEN the agent MUST generate the artifact in the active project

#### Scenario: review

- GIVEN the user says "Jarvis, que revise el último commit"
- WHEN executed
- THEN the system MUST report the identified risks (spoken + text)

### Requirement: Active project (RF-6)

The system MUST auto-detect the active project at startup (git cwd, else last known repo) and MUST support switching it by voice.

#### Scenario: Startup detection

- GIVEN the assistant starts inside a git repository
- THEN the active project MUST be that repository
- AND if no git repo is detected, the last known repository MUST be restored

#### Scenario: Voice switch

- GIVEN an active project is set
- WHEN the user says "Jarvis, trabajá en anubis-api"
- THEN the active project MUST switch to anubis-api
- AND subsequent OpenCode commands MUST target it

### Requirement: Offline degradation (M4)

When network/LLM service is unavailable, OpenCode commands MUST fail with a spoken notice that network is required. System, file, and web actions MUST keep working.

#### Scenario: No network

- GIVEN the machine is offline
- WHEN the user asks an OpenCode question
- THEN the system MUST reply that network is required for that command
- AND a system command (e.g. shutdown) MUST still work
