from shared.models import AgentRole
from shared.worker import AgentHandler

from .infra_ops import execute as infra_execute
from .cloud_ops import execute as cloud_execute

AGENT_REGISTRY: dict[str, AgentHandler] = {
    AgentRole.INFRA_OPS: infra_execute,
    AgentRole.CLOUD_OPS: cloud_execute,
}
