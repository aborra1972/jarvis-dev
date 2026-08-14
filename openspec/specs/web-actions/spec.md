# web-actions Specification

## Purpose

Performs web searches and opens URLs directly in the default browser via xdg-open (RF-10). The MVP opens the browser directly for searches (no spoken result summary). Executor is an in-process module (RNF-5).

## Requirements

### Requirement: Web search opens browser (RF-10)

`web_search` MUST open the default browser directly with the search query for the configured engine.

#### Scenario: Happy path

- GIVEN the user says "Jarvis, buscá en internet qué es openwakeword"
- WHEN executed
- THEN the default browser MUST open with the search query

#### Scenario: Browser failure

- GIVEN xdg-open fails or no browser is available
- WHEN `web_search` is executed
- THEN the system MUST report a spoken error
- AND MUST NOT fall back to partial execution

### Requirement: Open URL (RF-10)

`open_url` MUST validate the URL and open it in the default browser.

#### Scenario: Valid URL

- GIVEN the user says "Jarvis, abrí https://docs.opencode.ai"
- WHEN executed
- THEN the URL MUST open in the default browser

#### Scenario: Malformed URL

- GIVEN the user says "Jarvis, abrí <not-a-url>"
- WHEN validated
- THEN the system MUST report a spoken error
- AND MUST NOT open anything
