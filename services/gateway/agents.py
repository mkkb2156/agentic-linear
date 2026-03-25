"""Central agent registry — registers all 10 agents with the dispatcher."""

from __future__ import annotations

from shared.dispatcher import AgentDispatcher
from shared.models import AgentRole

from services.planning.agents.product_strategist import execute as product_strategist_execute
from services.planning.agents.spec_architect import execute as spec_architect_execute
from services.planning.agents.system_architect import execute as system_architect_execute
from services.build.agents.frontend_engineer import execute as frontend_execute
from services.build.agents.backend_engineer import execute as backend_execute
from services.verify.agents.qa_engineer import execute as qa_execute
from services.verify.agents.devops import execute as devops_execute
from services.verify.agents.release_manager import execute as release_execute
from services.ops.agents.infra_ops import execute as infra_execute
from services.ops.agents.cloud_ops import execute as cloud_execute
from services.admin.agents.admin_agent import execute as admin_execute


def register_all_agents(dispatcher: AgentDispatcher) -> None:
    """Register all 11 pipeline agents with the dispatcher."""
    dispatcher.register(AgentRole.PRODUCT_STRATEGIST, product_strategist_execute)
    dispatcher.register(AgentRole.SPEC_ARCHITECT, spec_architect_execute)
    dispatcher.register(AgentRole.SYSTEM_ARCHITECT, system_architect_execute)
    dispatcher.register(AgentRole.FRONTEND_ENGINEER, frontend_execute)
    dispatcher.register(AgentRole.BACKEND_ENGINEER, backend_execute)
    dispatcher.register(AgentRole.QA_ENGINEER, qa_execute)
    dispatcher.register(AgentRole.DEVOPS, devops_execute)
    dispatcher.register(AgentRole.RELEASE_MANAGER, release_execute)
    dispatcher.register(AgentRole.INFRA_OPS, infra_execute)
    dispatcher.register(AgentRole.CLOUD_OPS, cloud_execute)
    dispatcher.register(AgentRole.ADMIN, admin_execute)
