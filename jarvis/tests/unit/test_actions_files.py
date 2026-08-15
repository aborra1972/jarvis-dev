"""File executors (PR4, task 4.5): create_doc new-only, open_file_dir.

Design (RF-9, threat matrix): create_doc never overwrites/edits/deletes —
exclusive_write (O_EXCL) fails on an existing name and degrades to a spoken
error; open_file_dir only opens (xdg-open) the project dir or an existing
named file. No shell, list-args only.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.actions import files
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.session import Session


def _intent(name, entities=None, **overrides):
    kwargs = {"intent": name, "entities": entities or {}, "confidence": 0.9}
    kwargs.update(overrides)
    return Intent(**kwargs)


def _commands(monkeypatch):
    commands = []
    monkeypatch.setattr(
        files.base,
        "safe_run",
        lambda command, timeout=20.0: commands.append(command) or (0, ""),
    )
    return commands


# --- create_doc --------------------------------------------------------------
def test_create_doc_writes_slugged_name_in_project(tmp_path) -> None:
    session = Session(active_project=str(tmp_path))
    result = files.create_doc(
        _intent("create_doc", {"text": "un documento con el resumen del sprint"}), session
    )
    assert result.ok is True
    target = tmp_path / "un-documento-con-el.md"
    assert target.read_text() == "un documento con el resumen del sprint"


def test_create_doc_never_overwrites_existing_file(tmp_path) -> None:
    target = tmp_path / "resumen.md"
    target.write_text("original")
    session = Session(active_project=str(tmp_path))
    result = files.create_doc(_intent("create_doc", {"text": "resumen"}), session)
    assert result.ok is False
    assert "ya existe" in result.spoken
    assert target.read_text() == "original"


def test_create_doc_falls_back_to_cwd_without_active_project(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = files.create_doc(_intent("create_doc", {"text": "nota"}), Session())
    assert result.ok is True
    assert (tmp_path / "nota.md").exists()


def test_create_doc_invalid_project_path_reports_spoken_error(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("soy un archivo, no una carpeta")
    session = Session(active_project=str(blocker))
    result = files.create_doc(_intent("create_doc", {"text": "nota"}), session)
    assert result.ok is False
    assert "no pude crear" in result.spoken
    assert not list(blocker.glob("*.md"))


def test_create_doc_missing_parent_dir_reports_spoken_error(tmp_path) -> None:
    session = Session(active_project=str(tmp_path / "no-existe"))
    result = files.create_doc(_intent("create_doc", {"text": "nota"}), session)
    assert result.ok is False
    assert "no pude crear" in result.spoken
    assert not (tmp_path / "no-existe" / "nota.md").exists()


# --- open_file_dir ------------------------------------------------------------
def test_open_file_dir_opens_active_project_dir(tmp_path, monkeypatch) -> None:
    commands = _commands(monkeypatch)
    session = Session(active_project=str(tmp_path))
    result = files.open_file_dir(_intent("open_file_dir", {"text": ""}), session)
    assert result.ok is True
    assert commands == [["xdg-open", str(tmp_path)]]


def test_open_file_dir_opens_named_existing_file_parent(tmp_path, monkeypatch) -> None:
    commands = _commands(monkeypatch)
    doc = tmp_path / "sub" / "doc.md"
    doc.parent.mkdir()
    doc.write_text("x")
    session = Session(active_project=str(tmp_path))
    result = files.open_file_dir(_intent("open_file_dir", {"text": "sub/doc.md"}), session)
    assert result.ok is True
    assert commands == [["xdg-open", str(doc.parent)]]


def test_open_file_dir_degrades_when_project_missing(tmp_path, monkeypatch) -> None:
    commands = _commands(monkeypatch)
    session = Session(active_project=str(tmp_path / "missing"))
    result = files.open_file_dir(_intent("open_file_dir", {"text": ""}), session)
    assert result.ok is False
    assert commands == []
