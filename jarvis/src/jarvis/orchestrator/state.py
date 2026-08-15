"""Orchestrator FSM (PR3, task 3.1).

Design states: idle → listening → confirming → executing → speaking → idle,
plus the RF-11 switch ``off`` state (never re-activated by voice) and the
terminal ``stopped`` state after ``power_off_self`` executes. Pure, table-driven
state machine: ``transition(state, event)`` returns the target state or raises
``InvalidTransition``. The loop (PR3) and executors (PR4) drive these events.
"""

from __future__ import annotations

from enum import Enum


class State(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    CONFIRMING = "confirming"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    OFF = "off"
    STOPPED = "stopped"


class Event(Enum):
    WAKE = "wake"
    SILENCE = "silence"
    INTENT_READY = "intent_ready"
    INTENT_DESTRUCTIVE = "intent_destructive"
    NEEDS_REASK = "needs_reask"
    REASK_EXHAUSTED = "reask_exhausted"
    REJECTED = "rejected"
    UNSUPPORTED = "unsupported"
    CONFIRM = "confirm"
    ABORT = "abort"
    TIMEOUT = "timeout"
    EXECUTE_DONE = "execute_done"
    EXECUTE_FAILED = "execute_failed"
    SPEAK_DONE = "speak_done"
    SWITCH_OFF = "switch_off"
    SWITCH_ON = "switch_on"
    POWER_OFF = "power_off"


class InvalidTransition(ValueError):
    def __init__(self, state: State, event: Event) -> None:
        super().__init__(f"invalid transition: {state.value} + {event.value}")
        self.state = state
        self.event = event


_TRANSITIONS: dict[tuple[State, Event], State] = {
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


def can_transition(state: State, event: Event) -> bool:
    return (state, event) in _TRANSITIONS


def transition(state: State, event: Event) -> State:
    try:
        return _TRANSITIONS[(state, event)]
    except KeyError:
        raise InvalidTransition(state, event) from None


def valid_events(state: State) -> tuple[Event, ...]:
    return tuple(event for (source, event) in _TRANSITIONS if source is state)
