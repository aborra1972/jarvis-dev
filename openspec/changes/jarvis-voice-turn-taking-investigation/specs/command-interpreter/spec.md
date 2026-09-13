# Delta for command-interpreter

## MODIFIED Requirements

### Requirement: Deterministic standalone goodbye control

The interpreter MUST recognize only the exact standalone utterances `terminamos` and `hasta luego` as the goodbye control. Goodbye recognition MUST be deterministic, MUST NOT depend on an LLM, and MUST fail closed for ambiguous, quoted, mentioned, reported, negated, embedded, or content occurrences. A goodbye MUST be routed as lifecycle control rather than as a new general, dictation-content, safety-critical, or destructive command. GUI-off state MUST take precedence outside interpretation so an off transition cannot be converted into goodbye handling.
(Previously: Exact deterministic goodbye control was required, but the turn-taking precedence relationship with GUI off and safety-critical routing was not explicit.)

#### Scenario: Exact goodbye

- GIVEN an active conversation
- WHEN the transcript is exactly `terminamos` or exactly `hasta luego`, ignoring only permitted transcript boundary normalization
- THEN the interpreter MUST emit the goodbye control
- AND MUST NOT emit an ordinary action intent

#### Scenario: Content is not goodbye

- GIVEN an active conversation
- WHEN the transcript contains a goodbye phrase as part of a longer request, quotation, mention, report, negation, or ambiguous text
- THEN the interpreter MUST NOT emit goodbye
- AND the transcript MUST remain available to ordinary interpretation or re-ask handling

#### Scenario: Goodbye is not destructive authorization

- GIVEN a destructive or safety-critical action is awaiting interpretation or confirmation
- WHEN the transcript is an exact standalone goodbye
- THEN the interpreter MUST emit lifecycle goodbye control only
- AND it MUST NOT emit `shutdown`, `reboot`, `power_off_self`, or an affirmative confirmation intent

### Requirement: Goodbye precedence in dictation

During dictation, a standalone approved goodbye MUST take control precedence over ordinary dictated content. Quoted, mentioned, negated, reported, ambiguous, embedded, or non-standalone occurrences MUST remain dictated data and MUST NOT close the conversation. Existing dictation controls and text-injection behavior MUST remain unchanged except for this exact standalone lifecycle control.
(Previously: Standalone goodbye precedence in dictation was required, but preservation of existing dictation behavior was not explicit.)

#### Scenario: Standalone dictation control

- GIVEN dictation mode is active
- WHEN the standalone transcript is `hasta luego`
- THEN the interpreter MUST classify it as goodbye control
- AND MUST NOT append it as dictated content

#### Scenario: Quoted dictation content

- GIVEN dictation mode is active
- WHEN the user dictates content such as `escribí "hasta luego" en la nota`
- THEN the goodbye words MUST remain dictated data
- AND the conversation MUST remain active

#### Scenario: Existing dictation commands are preserved

- GIVEN dictation mode is active
- WHEN the user gives an existing dictation command such as send, clear, or exit dictation
- THEN the dictation command MUST keep its existing behavior
- AND the new goodbye lifecycle rule MUST NOT broaden or replace those controls
