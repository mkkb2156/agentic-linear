from shared.dispatcher import AgentHandler
from shared.models import AgentRole

from .frontend_engineer import execute as frontend_execute
from .backend_engineer import execute as backend_execute

AGENT_REGISTRY: dict[str, AgentHandler] = {
    AgentRole.FRONTEND_ENGINEER: frontend_execute,
    AgentRole.BACKEND_ENGINEER: backend_execute,
}
