from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.dream import DreamConsolidator


@pytest.fixture
def tmp_souls_dir(tmp_path: Path) -> Path:
    d = tmp_path / "souls"
    d.mkdir()
    return d


@pytest.fixture
def tmp_projects_dir(tmp_path: Path) -> Path:
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
def consolidator(tmp_souls_dir: Path, tmp_projects_dir: Path) -> DreamConsolidator:
    from shared.soul_manager import SoulManager
    from shared.project_context import ProjectContextManager

    return DreamConsolidator(
        api_key="test-key",
        soul_manager=SoulManager(souls_dir=tmp_souls_dir),
        project_context_manager=ProjectContextManager(projects_dir=tmp_projects_dir),
        learnings_reader=lambda role=None: "no learnings",
    )


class TestDreamConsolidator:
    @pytest.mark.asyncio
    async def test_dream_soul_calls_api(self, consolidator: DreamConsolidator) -> None:
        consolidator._soul.write("frontend_engineer", "# Soul\n\n## 技術經驗\n- old entry")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="# Soul\n\n## 技術經驗\n- consolidated entry")]

        with patch.object(
            consolidator, "_call_claude", new_callable=AsyncMock, return_value=mock_response
        ):
            await consolidator.dream_soul("frontend_engineer")

        content = consolidator._soul.load("frontend_engineer")
        assert "consolidated entry" in content

    @pytest.mark.asyncio
    async def test_dream_project_calls_api(self, consolidator: DreamConsolidator) -> None:
        consolidator._project_ctx.write("proj-1", "# Context\n\n## Requirements\n- old req")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="# Context\n\n## Requirements\n- new req")]

        with patch.object(
            consolidator, "_call_claude", new_callable=AsyncMock, return_value=mock_response
        ):
            await consolidator.dream_project("proj-1")

        content = consolidator._project_ctx.load("proj-1")
        assert "new req" in content

    @pytest.mark.asyncio
    async def test_dream_skips_empty_soul(self, consolidator: DreamConsolidator) -> None:
        with patch.object(consolidator, "_call_claude", new_callable=AsyncMock) as mock:
            await consolidator.dream_soul("nonexistent")
        mock.assert_not_called()
