from __future__ import annotations

from pathlib import Path

import pytest

from shared.project_context import ProjectContextManager


@pytest.fixture
def tmp_projects_dir(tmp_path: Path) -> Path:
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
def manager(tmp_projects_dir: Path) -> ProjectContextManager:
    return ProjectContextManager(projects_dir=tmp_projects_dir)


class TestProjectContextManager:
    def test_load_empty(self, manager: ProjectContextManager) -> None:
        assert manager.load("proj-1") == ""

    def test_append_and_load(self, manager: ProjectContextManager) -> None:
        manager.append("proj-1", "requirement", "B2B 電商賣家", project_name="ad-fast")
        content = manager.load("proj-1")
        assert "B2B" in content
        assert "Requirements" in content

    def test_append_multiple_categories(self, manager: ProjectContextManager) -> None:
        manager.append("proj-1", "requirement", "圖片批量生成", project_name="ad-fast")
        manager.append("proj-1", "decision", "用 Sharp 不用 Canvas", project_name="ad-fast")
        content = manager.load("proj-1")
        assert "Sharp" in content
        assert "Requirements" in content
        assert "Decisions" in content

    def test_write_replaces_content(self, manager: ProjectContextManager) -> None:
        manager.append("proj-1", "requirement", "old", project_name="ad-fast")
        manager.write("proj-1", "# new content only")
        content = manager.load("proj-1")
        assert "new content only" in content
        assert "old" not in content

    def test_line_count(self, manager: ProjectContextManager) -> None:
        manager.write("proj-1", "\n".join([f"- line {i}" for i in range(80)]))
        assert manager.line_count("proj-1") == 80
