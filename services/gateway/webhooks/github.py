from __future__ import annotations

from fastapi import APIRouter, Response

router = APIRouter()


@router.post("/github")
async def github_webhook() -> Response:
    """Placeholder for GitHub webhook handler (Phase 3)."""
    return Response(status_code=200)
