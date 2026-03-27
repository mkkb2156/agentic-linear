"""Agent Soul — persistent cross-project memory per agent.

Each agent has a soul file (markdown) that records technical experience,
collaboration patterns, past mistakes, and preferences.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

SOULS_DIR = Path(__file__).resolve().parent / "agent_config" / "souls"


class SoulManager:
    def __init__(self, souls_dir: Path | None = None) -> None:
        self._dir = souls_dir or SOULS_DIR

    def load(self, role: str) -> str:
        path = self._dir / f"{role}.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def write(self, role: str, content: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{role}.md"
        path.write_text(content, encoding="utf-8")
        logger.info("Soul updated: %s", path)

    def append(self, role: str, category: str, entry: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{role}.md"
        today = date.today().isoformat()
        tagged_entry = f"- [{today}] {entry}"

        if not path.exists():
            content = f"# {role} — Soul\n\n## {category}\n{tagged_entry}\n"
            path.write_text(content, encoding="utf-8")
            return

        content = path.read_text(encoding="utf-8")
        section_header = f"## {category}"
        if section_header in content:
            idx = content.index(section_header) + len(section_header)
            newline_idx = content.index("\n", idx)
            content = content[:newline_idx + 1] + tagged_entry + "\n" + content[newline_idx + 1:]
        else:
            content = content.rstrip() + f"\n\n{section_header}\n{tagged_entry}\n"

        path.write_text(content, encoding="utf-8")

    def line_count(self, role: str) -> int:
        content = self.load(role)
        if not content:
            return 0
        return len(content.split("\n"))
