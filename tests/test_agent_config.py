"""Tests for AgentConfigManager."""

from pathlib import Path

import pytest

from shared.agent_config import AgentConfig, AgentConfigManager


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a temporary agent_config directory structure."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "agents").mkdir()
    (tmp_path / "learnings").mkdir()

    # Global rules
    (tmp_path / "claude.md").write_text("# Global Rules\nUse Traditional Chinese.\n")

    # A skill file
    (tmp_path / "skills" / "supabase.md").write_text("# Supabase\nRLS best practices.\n")
    (tmp_path / "skills" / "nextjs.md").write_text("# Next.js\nApp Router patterns.\n")

    # An agent config
    import yaml

    agent_cfg = {"role": "frontend_engineer", "model": "sonnet", "max_turns": 15, "skills": ["nextjs"], "enabled": True}
    (tmp_path / "agents" / "frontend_engineer.yaml").write_text(yaml.dump(agent_cfg))

    return tmp_path


@pytest.fixture
def mgr(config_dir: Path) -> AgentConfigManager:
    return AgentConfigManager(config_dir=config_dir)


def test_load_agent_config(mgr: AgentConfigManager) -> None:
    cfg = mgr.load_agent_config("frontend_engineer")
    assert cfg is not None
    assert cfg.role == "frontend_engineer"
    assert cfg.model == "sonnet"
    assert cfg.skills == ["nextjs"]
    assert cfg.enabled is True


def test_missing_config_returns_none(mgr: AgentConfigManager) -> None:
    cfg = mgr.load_agent_config("nonexistent_agent")
    assert cfg is None


def test_build_system_prompt_combines_sources(mgr: AgentConfigManager) -> None:
    base = "You are the Frontend Engineer."
    prompt = mgr.build_system_prompt("frontend_engineer", base)

    assert "Global Rules" in prompt
    assert "Traditional Chinese" in prompt
    assert "Next.js" in prompt
    assert "App Router" in prompt
    assert "Frontend Engineer" in prompt
    # Supabase should NOT be included (not in skills list)
    assert "Supabase" not in prompt


def test_build_system_prompt_fallback_no_config(mgr: AgentConfigManager) -> None:
    """When no YAML exists, just concatenates claude.md + base_prompt."""
    base = "You are the QA Engineer."
    prompt = mgr.build_system_prompt("qa_engineer", base)

    assert "Global Rules" in prompt
    assert "QA Engineer" in prompt


def test_list_skills(mgr: AgentConfigManager) -> None:
    skills = mgr.list_skills()
    assert "supabase" in skills
    assert "nextjs" in skills


def test_read_skill(mgr: AgentConfigManager) -> None:
    content = mgr.read_skill("supabase")
    assert "RLS" in content


def test_write_skill(mgr: AgentConfigManager) -> None:
    mgr.write_skill("testing", "# Testing\npytest best practices.")
    assert "testing" in mgr.list_skills()
    assert "pytest" in mgr.read_skill("testing")


def test_update_agent_config(mgr: AgentConfigManager) -> None:
    mgr.update_agent_config("frontend_engineer", {"max_turns": 20, "skills": ["nextjs", "supabase"]})
    cfg = mgr.load_agent_config("frontend_engineer")
    assert cfg is not None
    assert cfg.max_turns == 20
    assert cfg.skills == ["nextjs", "supabase"]


def test_append_and_read_learnings(mgr: AgentConfigManager) -> None:
    mgr.append_learning("spec_architect | DRO-42 | HIGH_TOKEN | 8000 tokens")
    mgr.append_learning("frontend_engineer | DRO-43 | FAIL | timeout")

    log = mgr.read_learnings()
    assert "spec_architect" in log
    assert "FAIL" in log
    assert log.count("\n") == 2  # Two entries


def test_empty_learnings(mgr: AgentConfigManager) -> None:
    assert mgr.read_learnings() == ""
