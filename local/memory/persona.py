"""Load persona files. They are not the user profile store."""

from __future__ import annotations

from pathlib import Path

PERSONA_DIR = Path(__file__).resolve().parent.parent / "persona"
PERSONA_FILES = ("SOUL.md", "IDENTITY.md")


def persona_paths() -> list[Path]:
    return [PERSONA_DIR / name for name in PERSONA_FILES]


def load_persona_text() -> str:
    parts: list[str] = []
    for path in persona_paths():
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def persona_system_block(text: str | None = None) -> str:
    """Wrap persona text. ``None`` reads the global SOUL and IDENTITY files."""
    if text is None:
        text = load_persona_text()
    text = (text or "").strip()
    if not text:
        return ""
    if text.startswith("<persona>") and text.endswith("</persona>"):
        return text
    return f"<persona>\n{text}\n</persona>"