from shared.models import AgentRole
from shared.worker import AgentHandler

from .product_strategist import execute as product_strategist_execute
from .spec_architect import execute as spec_architect_execute
from .system_architect import execute as system_architect_execute

AGENT_REGISTRY: dict[str, AgentHandler] = {
    AgentRole.PRODUCT_STRATEGIST: product_strategist_execute,
    AgentRole.SPEC_ARCHITECT: spec_architect_execute,
    AgentRole.SYSTEM_ARCHITECT: system_architect_execute,
}
