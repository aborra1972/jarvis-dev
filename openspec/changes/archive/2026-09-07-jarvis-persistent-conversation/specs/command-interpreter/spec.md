# Delta for Command Interpreter

## Scope and traceability

Approved proposal slice 2 and finite-confirmation integration. Existing names remain archive keys; PC-C identifiers are stable references. Golden rule gate for destructive intents, Allowlist, no arbitrary shell, and Re-ask then reveal (RNF-4), including both re-ask scenarios and the manual-correction fallback, remain unchanged. PC-S01 defines the existing verbal gate's precise deadline. Conversation control adds no agent command.

## MODIFIED Requirements

### Requirement: LLM-first intent resolution (RF-2, RF-3)

[PC-C02] The interpreter MUST resolve non-critical action requests from free natural language using the configured LLM provider. It MUST map resolved action requests to exactly one of the 15 allowlisted commands and MUST NOT produce actions outside the allowlist. Explicit conversation goodbye under PC-C01 MUST be handled as conversation control rather than an action request or new command; the LLM MUST NOT reinterpret that control as power_off_self or another action.
(Previously: Utterances were mapped to the 15-command allowlist without an explicit conversation-control exception.)

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

- GIVEN the user request is outside the allowlist and is not explicit conversation goodbye
- WHEN the interpreter cannot map it to a command
- THEN it MUST NOT execute anything
- AND it MUST trigger the re-ask flow

## ADDED Requirements

### Requirement: Explicit goodbye and control precedence

[PC-C01] In an active conversation, unquoted, non-negated "terminamos" or "hasta luego" used as a standalone explicit goodbye MUST close conversation under PC-L02 without emitting an agent command, shutdown, reboot, or power_off_self. Quoted, negated, mentioned, or dictated occurrences MUST NOT be treated as closure merely because those words occur. Dictation content MUST retain its data meaning; explicit goodbye outside that content MUST retain its control meaning. Ambiguous text MUST NOT be guessed into closure or dangerous authorization. Exact parsing and concurrent-mode mechanisms remain design choices constrained by these outcomes.

Explicit goodbye MUST take precedence over pending-confirmation classification and ordinary action resolution. Recognizing it MUST invalidate pending authorization before any not-yet-started dangerous execution; it MUST NOT count as an affirmative or trigger a re-ask that keeps stale authorization alive. GUI off MUST take precedence over goodbye and any completion/listening transition. Existing speaker gates, golden rules, the action allowlist, and finite confirmation MUST NOT be bypassed by an open conversation.

#### Scenario: Exact goodbye

- GIVEN an active conversation with no dictation-content context
- WHEN the user says exactly "terminamos" or "hasta luego" as goodbye
- THEN the system MUST close conversation and return to wake standby
- AND it MUST NOT dispatch an agent command, power off, exit, or request destructive confirmation

#### Scenario: Quoted mention

- GIVEN an active conversation
- WHEN the user says "¿qué significa 'hasta luego'?" or "explicá la palabra 'terminamos'"
- THEN those mentions MUST NOT close conversation or authorize a pending action
- AND the ordinary request MUST remain subject to the existing interpreter gates

#### Scenario: Negated goodbye

- GIVEN an active conversation
- WHEN the user says "no terminamos" or "no quiero decir hasta luego"
- THEN the system MUST NOT treat that utterance as explicit goodbye or affirmative authorization

#### Scenario: Dictation preserves content

- GIVEN the user is supplying dictation content, including a content turn consisting of "terminamos"
- WHEN the text includes "hasta luego", "terminamos", or "escribí 'hasta luego'" as data
- THEN those words MUST remain content rather than conversation control
- AND their presence MUST NOT close conversation or authorize a dangerous action

#### Scenario: Explicit control outside dictation content

- GIVEN dictation has ended or the utterance is unambiguously outside its content
- WHEN the user explicitly says "hasta luego" as goodbye
- THEN it MUST close conversation rather than append a new dictated command or invoke power_off_self

#### Scenario: Goodbye while confirmation is pending

- GIVEN a dangerous action awaits confirmation
- WHEN the user explicitly says "terminamos" or "hasta luego" as goodbye
- THEN goodbye control MUST invalidate pending authorization and close conversation
- AND it MUST NOT be classified as consent or passed to ordinary action resolution
- AND a late affirmative/STT result MUST NOT execute the invalidated action

#### Scenario: Off and goodbye overlap

- GIVEN goodbye handling would restore wake standby
- WHEN GUI off takes effect concurrently
- THEN the assistant MUST remain off and MUST NOT reopen the microphone or react to the wake word
