"""Event router — DAG-enforced pipeline routing.

Routes Linear webhook events to agent handlers via the dispatcher.
Linear is the source of truth; no intermediate database queue.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.agent_base import AgentTask
from shared.dispatcher import AgentDispatcher
from shared.models import (
    PIPELINE_ORDER,
    PIPELINE_TRANSITIONS,
    LinearWebhookPayload,
    StatusTransition,
)

logger = logging.getLogger(__name__)

# Build lookup: status name → list of transitions (some statuses trigger multiple agents)
_TRANSITION_MAP: dict[str, list[StatusTransition]] = {}
for t in PIPELINE_TRANSITIONS:
    _TRANSITION_MAP.setdefault(t.from_status, []).append(t)

# Build stage index for DAG enforcement
_STAGE_INDEX: dict[str, int] = {s: i for i, s in enumerate(PIPELINE_ORDER)}


class EventRouter:
    def __init__(self, dispatcher: AgentDispatcher) -> None:
        self._dispatcher = dispatcher

    async def route(self, event: LinearWebhookPayload, delivery_id: str | None = None) -> int:
        """
        Route a Linear webhook event to the appropriate agent(s).
        Returns the number of agents dispatched.
        """
        if event.action != "update" or event.type != "Issue":
            return 0

        # Extract status change
        new_state = _get_nested(event.data, "state", "name")
        old_state = _get_nested(event.updated_from or {}, "state", "name") if event.updated_from else None

        if not new_state or not old_state:
            return 0

        # DAG enforcement: only allow forward transitions
        if not self._is_forward_transition(old_state, new_state):
            logger.warning(
                "Blocked backward transition: %s → %s",
                old_state,
                new_state,
            )
            return 0

        # Look up target agents
        transitions = _TRANSITION_MAP.get(new_state, [])
        if not transitions:
            logger.debug("No pipeline transition for status: %s", new_state)
            return 0

        issue_id = event.data.get("identifier", event.data.get("id", "unknown"))
        dispatched = 0

        for transition in transitions:
            task = AgentTask(
                issue_id=issue_id,
                agent_role=transition.agent_role,
                payload={
                    "event": event.model_dump(),
                    "old_status": old_state,
                    "new_status": new_state,
                },
            )

            success = await self._dispatcher.dispatch(
                agent_role=transition.agent_role,
                task=task,
                delivery_id=delivery_id,
            )
            if success:
                dispatched += 1

        logger.info(
            "Routed %s → %s: %d agent(s) dispatched for %s",
            old_state,
            new_state,
            dispatched,
            issue_id,
        )
        return dispatched

    @staticmethod
    def _is_forward_transition(old_status: str, new_status: str) -> bool:
        """Check that the transition goes forward in the pipeline DAG."""
        old_idx = _STAGE_INDEX.get(old_status)
        new_idx = _STAGE_INDEX.get(new_status)

        # If either status is not in the pipeline order, allow it
        # (it may be a custom status or initial creation)
        if old_idx is None or new_idx is None:
            return True

        return new_idx >= old_idx


def _get_nested(d: dict[str, Any], *keys: str) -> Any:
    """Safely get a nested dictionary value."""
    for key in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(key)  # type: ignore[assignment]
    return d
