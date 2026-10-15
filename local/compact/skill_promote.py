"""Write a confirmed procedural candidate as a LightAgent skill."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .types import ProceduralCandidate


def default_skills_dir() -> Path:
    """Directory scanned like any other ``skills_directories`` entry."""
    return Path(__file__).resolve().parents[1] / "skills_promoted" / "skills"


def _slug(title: str, candidate_id: str) -> str:
    ascii_part = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    if not ascii_part or not re.search(r"[a-z0-9]", ascii_part):
        ascii_part = "procedure"
    suffix = re.sub(r"[^a-z0-9]", "", candidate_id.lower())[:6] or "skill"
    return f"{ascii_part}-{suffix}"[:48]


def render_skill_markdown(candidate: ProceduralCandidate, *, name: str) -> str:
    description = candidate.description.strip() or candidate.title
    front = yaml.safe_dump(
        {"name": name, "description": description[:240]},
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    steps = candidate.steps or (candidate.source_text,)
    body = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    return (
        f"---\n{front}\n---\n\n"
        f"# {candidate.title}\n\n"
        f"{body}\n"
    )


def promote_skill(candidate: ProceduralCandidate, skills_dir: str | Path | None = None) -> Path:
    """Create ``<skills_dir>/<slug>/SKILL.md`` and return the skill directory."""
    root = Path(skills_dir) if skills_dir is not None else default_skills_dir()
    root.mkdir(parents=True, exist_ok=True)
    name = _slug(candidate.title, candidate.id)
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(render_skill_markdown(candidate, name=name), encoding="utf-8")
    return folder


def register_skills_directory(agent: object, skills_dir: str | Path) -> None:
    """Append the directory and rediscover skills when the agent has a manager."""
    directory = str(skills_dir)
    current = list(getattr(agent, "skills_directories", None) or [])
    if directory not in current:
        current.append(directory)
        setattr(agent, "skills_directories", current)
    manager = getattr(agent, "skill_manager", None)
    if manager is not None:
        manager.skills_directories = current
        manager.discover_skills()
