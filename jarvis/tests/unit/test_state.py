"""Orchestrator FSM tests (PR3, task 3.1).

Table-driven: every (state, event) pair is asserted against an authoritative
expected table — valid pairs land on the expected state, invalid pairs raise
InvalidTransition. Encodes the design FSM (idle/listening/confirming/executing/
speaking), the RF-11 switch off state, and the power-off terminal.
"""

from __future__ import annotations

import pytest

from jarvis.orchestrator.state import (
    Event,
    InvalidTransition,
    State,
    can_transition,
    transition,
    valid_events,
)

EXPECTED: dict[tuple[State, Event], State] = {
    (State.IDLE, Event.WAKE): State.LISTENING,
    (State.IDLE, Event.SWITCH_OFF): State.OFF,
    (State.LISTENING, Event.SILENCE): State.IDLE,
    (State.LISTENING, Event.INTENT_READY): State.EXECUTING,
    (State.LISTENING, Event.INTENT_DESTRUCTIVE): State.CONFIRMING,
    (State.LISTENING, Event.NEEDS_REASK): State.LISTENING,
    (State.LISTENING, Event.REASK_EXHAUSTED): State.SPEAKING,
    (State.LISTENING, Event.REJECTED): State.SPEAKING,
    (State.LISTENING, Event.UNSUPPORTED): State.SPEAKING,
    (State.LISTENING, Event.SWITCH_OFF): State.OFF,
    (State.CONFIRMING, Event.CONFIRM): State.EXECUTING,
    (State.CONFIRMING, Event.ABORT): State.SPEAKING,
    (State.CONFIRMING, Event.TIMEOUT): State.SPEAKING,
    (State.CONFIRMING, Event.SWITCH_OFF): State.OFF,
    (State.EXECUTING, Event.EXECUTE_DONE): State.SPEAKING,
    (State.EXECUTING, Event.EXECUTE_FAILED): State.SPEAKING,
    (State.EXECUTING, Event.POWER_OFF): State.STOPPED,
    (State.SPEAKING, Event.SPEAK_DONE): State.IDLE,
    (State.SPEAKING, Event.SWITCH_OFF): State.OFF,
    (State.OFF, Event.SWITCH_ON): State.IDLE,
}


@pytest.mark.parametrize("state", list(State))
@pytest.mark.parametrize("event", list(Event))
def test_transition_table(state: State, event: Event) -> None:
    if (state, event) in EXPECTED:
        assert can_transition(state, event) is True
        assert transition(state, event) is EXPECTED[(state, event)]
    else:
        assert can_transition(state, event) is False
        with pytest.raises(InvalidTransition):
            transition(state, event)


def test_valid_events_match_table() -> None:
    for state in State:
        expected = frozenset(ev for (st, ev) in EXPECTED if st is state)
        assert frozenset(valid_events(state)) == expected


def test_wake_word_cannot_reactivate_from_off() -> None:
    assert can_transition(State.OFF, Event.WAKE) is False
    with pytest.raises(InvalidTransition):
        transition(State.OFF, Event.WAKE)


def test_off_reactivates_only_via_non_vocal_signal() -> None:
    assert transition(State.OFF, Event.SWITCH_ON) is State.IDLE


def test_stopped_is_terminal() -> None:
    assert valid_events(State.STOPPED) == ()


def test_full_cycle_wake_to_idle() -> None:
    s = State.IDLE
    s = transition(s, Event.WAKE)
    s = transition(s, Event.INTENT_DESTRUCTIVE)
    s = transition(s, Event.CONFIRM)
    s = transition(s, Event.EXECUTE_DONE)
    s = transition(s, Event.SPEAK_DONE)
    assert s is State.IDLE
