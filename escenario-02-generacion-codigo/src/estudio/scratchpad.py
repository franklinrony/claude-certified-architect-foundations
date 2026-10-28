"""Hallazgos en un archivo, para no depender de un contexto que ya se llenó."""

from pathlib import Path


def record(path: Path, finding: str) -> None:
    text = finding.strip()
    if not text:
        raise ValueError("finding must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    separator = "" if previous.endswith("\n") or not previous else "\n"
    path.write_text(previous + separator + text + "\n", encoding="utf-8")


def read_findings(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
