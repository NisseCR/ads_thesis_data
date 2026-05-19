import json
from pathlib import Path


def save_text_to_file(file_path: Path, text: str) -> None:
    """Write text content to a file, creating parent directories if needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text, encoding="utf-8")


def save_json_to_file(file_path: Path, data: object) -> None:
    """Write JSON data to a file, creating parent directories if needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_json_from_file(file_path: Path) -> object:
    """Read JSON data from a file."""
    return json.loads(file_path.read_text(encoding="utf-8"))