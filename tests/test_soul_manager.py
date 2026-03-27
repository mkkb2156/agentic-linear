from __future__ import annotations

from pathlib import Path

import pytest

from shared.soul_manager import SoulManager


@pytest.fixture
def tmp_souls_dir(tmp_path: Path) -> Path:
    d = tmp_path / "souls"
    d.mkdir()
    return d


@pytest.fixture
def manager(tmp_souls_dir: Path) -> SoulManager:
    return SoulManager(souls_dir=tmp_souls_dir)


class TestSoulManager:
    def test_load_empty(self, manager: SoulManager) -> None:
        assert manager.load("frontend_engineer") == ""

    def test_append_and_load(self, manager: SoulManager) -> None:
        manager.append("frontend_engineer", "技術經驗", "Sharp 處理大圖要設 limit")
        content = manager.load("frontend_engineer")
        assert "Sharp" in content
        assert "技術經驗" in content

    def test_append_multiple_categories(self, manager: SoulManager) -> None:
        manager.append("backend_engineer", "技術經驗", "Supabase RLS 注意事項")
        manager.append("backend_engineer", "踩過的坑", "Storage 5MB 限制")
        content = manager.load("backend_engineer")
        assert "Supabase RLS" in content
        assert "Storage 5MB" in content

    def test_write_replaces_content(self, manager: SoulManager) -> None:
        manager.append("qa_engineer", "技術經驗", "old entry")
        manager.write("qa_engineer", "# 🧪 QA Engineer — Soul\n\n## 技術經驗\n- new entry only")
        content = manager.load("qa_engineer")
        assert "new entry only" in content
        assert "old entry" not in content

    def test_line_count(self, manager: SoulManager) -> None:
        manager.write("devops", "\n".join([f"- line {i}" for i in range(120)]))
        assert manager.line_count("devops") == 120
