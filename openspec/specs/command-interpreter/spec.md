# command-interpreter Specification

## Purpose

Maps free-form rioplatense natural language to the 15-command allowlist. LLM-first for non-critical intents (via the configured OpenCode provider); a hard rule-based golden table gates critical/destructive intents (shutdown, reboot, power_off_self) so they never depend on the LLM. Re-asks up to 2× then reveals the raw transcript (RNF-4); never executes partially. One of the 5 runtime components (RNF-5).

## Requirements

### Requirement: LLM-first intent resolution (RF-2, RF-3)

The interpreter MUST resolve non-critical intents from free natural language using the configured LLM provider. It MUST map utterances to exactly one of the 15 allowlisted commands and MUST NOT produce actions outside the allowlist.

#### Scenario: Happy path

- GIVEN the user says "Jarvis, preguntale cómo funciona el middleware de auth"
- WHEN the interpreter resolves the intent
- THEN the result MUST be intent `ask` with the query as entity

#### Scenario: Rioplatense variants

- GIVEN the user says "Jarvis, abrime el repo anubis-api"
- WHEN the interpreter resolves the intent
- THEN the result MUST be intent `open_repo` with entity "anubis-api"
- AND variants ("abrí", "abrime", "podés abrir") MUST resolve to the same intent

#### Scenario: Unknown command

- GIVEN the user request is outside the allowlist
- WHEN the interpreter cannot map it to a command
- THEN it MUST NOT execute anything
- AND it MUST trigger the re-ask flow

### Requirement: Golden rule gate for destructive intents

Critical/destructive intents (shutdown, reboot, power_off_self) MUST be verified by a rule-based golden table that never depends on the LLM. If the golden table does not confirm the intent, the interpreter MUST NOT emit it for execution.

#### Scenario: Golden table confirms

- GIVEN the user says "Jarvis, cerrá Linux"
- WHEN the LLM suggests intent `shutdown`
- THEN the golden table MUST confirm the intent and entities
- AND the intent MUST proceed to the verbal confirmation gate (15s)

#### Scenario: LLM misinterpretation rejected

- GIVEN the user says "Jarvis, cerrá la ventana"
- WHEN the LLM resolves intent `shutdown` (misinterpretation)
- THEN the golden table MUST reject it
- AND no shutdown action MUST be emitted

#### Scenario: Ambiguous destructive utterance

- GIVEN the utterance is ambiguous (e.g. "apagá eso")
- WHEN the golden table cannot confirm shutdown/reboot/power_off_self
- THEN the intent MUST NOT be emitted
- AND the system MUST re-ask for clarification

### Requirement: Allowlist, no arbitrary shell

The interpreter MUST resolve only the 15 allowlisted commands. The system MUST NOT execute arbitrary shell commands, file edits, or deletions.

#### Scenario: Destructive out-of-scope request

- GIVEN the user says "Jarvis, borrá todos los archivos"
- WHEN the interpreter evaluates the request
- THEN it MUST reject it (not in allowlist)
- AND it MUST reply that the action is not supported

### Requirement: Re-ask then reveal (RNF-4)

When the interpreter cannot resolve an utterance with confidence, it MUST re-ask up to 2 times. After 2 failed attempts it MUST reveal the raw transcript and wait for manual correction. The system MUST NEVER execute a partial or ambiguous action.

#### Scenario: Re-ask resolves

- GIVEN the interpreter is unsure after the first pass
- WHEN the user clarifies (e.g. "no, al repo anubis-api")
- THEN the interpreter MUST resolve the clarified intent and proceed

#### Scenario: Two failed re-asks reveal transcript

- GIVEN two clarification attempts failed
- WHEN a third attempt still cannot be resolved
- THEN the system MUST show the raw transcript for manual correction
- AND MUST NOT execute anything
