"""Cuándo Claude Code entra en plan mode y cuándo edita directo.

plan mode y la ejecución directa son modos de Claude Code. No son campos de
la Messages API ni valores de stop_reason.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Change:
    files: tuple[str, ...]
    approaches: int = 1
    architectural: bool = False
    verbose_discovery: bool = False


@dataclass(frozen=True)
class WorkflowChoice:
    mode: str
    explore: bool


def choose_workflow(change: Change) -> WorkflowChoice:
    """Plan mode si el cambio es amplio o aún hay que elegir un diseño.

    Ejecución directa si el alcance es una sola función ya localizada.
    Explore, el subagente de Claude Code que resume una búsqueda larga,
    solo acompaña a plan mode. Así el hallazgo vuelve corto y el hilo
    principal no se llena de archivos.
    """
    if not change.files:
        raise ValueError("files must name at least one path")
    if change.approaches < 1:
        raise ValueError("approaches must be at least 1")
    needs_plan = change.architectural or change.approaches > 1 or len(change.files) > 1
    if needs_plan:
        return WorkflowChoice("plan_mode", change.verbose_discovery)
    return WorkflowChoice("direct_execution", False)


def memory_scope(path: str) -> str:
    """Dónde vive un CLAUDE.md. El de usuario no viaja con el repositorio."""
    normalized = path.replace("\\", "/")
    if normalized.startswith("~/") or normalized.startswith("~/.claude/"):
        return "user"
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts or parts[-1] != "CLAUDE.md":
        raise ValueError("path must end in CLAUDE.md")
    if len(parts) == 1 or parts == [".claude", "CLAUDE.md"]:
        return "project"
    return "directory"
