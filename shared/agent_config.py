"""Agent configuration system — skills loading, per-agent YAML config, learning log.

Directory structure:
    shared/agent_config/
        claude.md              — global rules (loaded for ALL agents)
        skills/*.md            — domain knowledge files
        agents/*.yaml          — per-agent config (skills, model, max_turns)
        learnings/learning_log.md — append-only learning log
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent / "agent_config"


class AgentConfig(BaseModel):
    role: str = ""
    model: str = "sonnet"
    max_turns: int = 15
    skills: list[str] = []
    enabled: bool = True


class AgentConfigManager:
    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or CONFIG_DIR

    @property
    def config_dir(self) -> Path:
        return self._dir

    # ---- Agent config (YAML) ----

    def load_agent_config(self, role: str) -> AgentConfig | None:
        """Load per-agent YAML config. Returns None if file doesn't exist."""
        path = self._dir / "agents" / f"{role}.yaml"
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            return AgentConfig(**data)
        except Exception as e:
            logger.error("Failed to load agent config %s: %s", path, e)
            return None

    def update_agent_config(self, role: str, updates: dict[str, Any]) -> None:
        """Update (or create) per-agent YAML config."""
        path = self._dir / "agents" / f"{role}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)

        existing: dict[str, Any] = {}
        if path.exists():
            with open(path) as f:
                existing = yaml.safe_load(f) or {}

        existing.update(updates)
        existing.setdefault("role", role)

        with open(path, "w") as f:
            yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)
        logger.info("Updated agent config: %s", path)

    # ---- System prompt building ----

    def build_system_prompt(
        self,
        role: str,
        base_prompt: str,
        *,
        soul_content: str = "",
        project_context: str = "",
        conversation_context: str = "",
    ) -> str:
        """Combine claude.md + skills + soul + project context + conversation + base_prompt."""
        parts: list[str] = []

        # 1. Global rules (claude.md)
        claude_md = self._dir / "claude.md"
        if claude_md.exists():
            parts.append(claude_md.read_text(encoding="utf-8").strip())

        # 2. Skills from agent config
        config = self.load_agent_config(role)
        if config and config.skills:
            for skill_name in config.skills:
                skill_content_str = self.read_skill(skill_name)
                if skill_content_str:
                    parts.append(f"## Skill: {skill_name}\n\n{skill_content_str}")

        # 3. Agent Soul (cross-project experience)
        if soul_content:
            parts.append(f"## 你的經驗記憶（跨專案）\n\n{soul_content}")

        # 4. Project Context (project-specific memory)
        if project_context:
            parts.append(f"## 專案脈絡\n\n{project_context}")

        # 5. Discord conversation context
        if conversation_context:
            parts.append(f"## Discord 對話脈絡\n\n{conversation_context}")

        # 6. Base prompt (hardcoded in agent class)
        parts.append(base_prompt)

        return "\n\n---\n\n".join(parts)

    # ---- Skills management ----

    def list_skills(self) -> list[str]:
        """List available skill file names (without .md extension)."""
        skills_dir = self._dir / "skills"
        if not skills_dir.exists():
            return []
        return sorted(p.stem for p in skills_dir.glob("*.md"))

    def read_skill(self, name: str) -> str:
        """Read a skill file's content. Returns empty string if not found."""
        path = self._dir / "skills" / f"{name}.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def write_skill(self, name: str, content: str) -> None:
        """Create or update a skill file."""
        path = self._dir / "skills" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info("Updated skill: %s", path)

    def delete_skill(self, name: str) -> None:
        """Delete a skill file."""
        path = self._dir / "skills" / f"{name}.md"
        if path.exists():
            path.unlink()
            logger.info("Deleted skill: %s", path)

    def get_agent_config(self, role: str) -> dict[str, Any]:
        """Load agent config as a dict (for API responses)."""
        config = self.load_agent_config(role)
        if config:
            return config.model_dump()
        return {"role": role, "model": "sonnet", "max_turns": 15, "skills": [], "enabled": True}

    # ---- Learning log ----

    def append_learning(self, entry: str) -> None:
        """Append a one-line learning entry with timestamp."""
        path = self._dir / "learnings" / "learning_log.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {entry}\n")

    def read_learnings(self) -> str:
        """Read the full learning log."""
        path = self._dir / "learnings" / "learning_log.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")


@lru_cache
def get_config_manager() -> AgentConfigManager:
    """Module-level singleton."""
    return AgentConfigManager()
