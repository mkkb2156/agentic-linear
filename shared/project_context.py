"""Project Context — per-project memory shared by all agents.

Stores requirements, decisions, constraints, and user preferences
discovered during the pipeline execution.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECTS_DIR = Path(__file__).resolve().parent.parent / "data" / "projects"

CATEGORY_HEADERS = {
    "requirement": "Requirements",
    "decision": "Decisions",
    "constraint": "Constraints",
    "user_preference": "User Preferences",
}


class ProjectContextManager:
    def __init__(self, projects_dir: Path | None = None) -> None:
        self._dir = projects_dir or PROJECTS_DIR

    def _context_path(self, project_id: str) -> Path:
        return self._dir / project_id / "context.md"

    def load(self, project_id: str) -> str:
        path = self._context_path(project_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def write(self, project_id: str, content: str) -> None:
        path = self._context_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info("Project context updated: %s", path)

    def append(
        self,
        project_id: str,
        category: str,
        content: str,
        project_name: str = "",
    ) -> None:
        path = self._context_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        section_name = CATEGORY_HEADERS.get(category, category.title())
        tagged_entry = f"- [{today}] {content}"

        if not path.exists():
            header = f"# {project_name or project_id} — Project Context"
            file_content = f"{header}\n\n## {section_name}\n{tagged_entry}\n"
            path.write_text(file_content, encoding="utf-8")
            return

        file_content = path.read_text(encoding="utf-8")
        section_header = f"## {section_name}"
        if section_header in file_content:
            idx = file_content.index(section_header) + len(section_header)
            newline_idx = file_content.index("\n", idx)
            file_content = (
                file_content[:newline_idx + 1]
                + tagged_entry + "\n"
                + file_content[newline_idx + 1:]
            )
        else:
            file_content = file_content.rstrip() + f"\n\n## {section_name}\n{tagged_entry}\n"

        path.write_text(file_content, encoding="utf-8")

    def line_count(self, project_id: str) -> int:
        content = self.load(project_id)
        if not content:
            return 0
        return len(content.split("\n"))

    def dream_log_path(self, project_id: str) -> Path:
        return self._dir / project_id / "dream_log.md"
