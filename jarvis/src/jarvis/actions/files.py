"""File executor (PR4, task 4.5): create_doc new-only, open_file_dir.

Design (RF-9, threat matrix): create_doc never overwrites/edits/deletes —
exclusive_write (O_EXCL) fails on an existing name and degrades to a spoken
error; open_file_dir only opens (xdg-open) the project dir or an existing
named file. All subprocess is list-args via base.safe_run (no shell).
"""

from __future__ import annotations

import re
from pathlib import Path

from jarvis.actions import base
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult
from jarvis.orchestrator.session import Session


def _slugify(text: str, words: int = 4) -> str:
    tokens = re.sub(r"[^a-z0-9 ]", "", text.lower()).split()
    return "-".join(tokens[:words])


def create_doc(intent: Intent, session: Session) -> ActionResult:
    content = intent.entities.get("text", "").strip()
    name = f"{_slugify(content) or 'documento'}.md"
    project = Path(session.active_project) if session.active_project else Path.cwd()
    target = project / name
    try:
        base.exclusive_write(target, content)
    except FileExistsError:
        return ActionResult(ok=False, spoken="ya existe un documento con ese nombre, elegí otro")
    return ActionResult(ok=True, spoken=f"creé {name}")


def open_file_dir(intent: Intent, session: Session) -> ActionResult:
    if not session.active_project:
        return ActionResult(ok=False, spoken="no tengo un proyecto activo")
    root = Path(session.active_project)
    name = intent.entities.get("text", "").strip()
    if name:
        candidate = root / name
        if candidate.is_file():
            root = candidate.parent
    if not root.is_dir():
        return ActionResult(ok=False, spoken="no encuentro esa carpeta")
    code, _ = base.safe_run(["xdg-open", str(root)])
    if code != 0:
        return ActionResult(ok=False, spoken="no pude abrir esa carpeta")
    return ActionResult(ok=True, spoken="abriendo carpeta")
