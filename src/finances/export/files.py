"""Write a CSV export to a local folder, never overwriting unless asked."""

from pathlib import Path

EXISTS = "the file is already there; add --force to replace it"


def write_csv(folder: Path, name: str, text: str, *, force: bool) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    if path.exists() and not force:
        raise ValueError(EXISTS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    return path
