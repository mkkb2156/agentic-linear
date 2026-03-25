from shared.models import AgentRole
from shared.worker import AgentHandler

from .qa_engineer import execute as qa_execute
from .devops import execute as devops_execute
from .release_manager import execute as release_execute

AGENT_REGISTRY: dict[str, AgentHandler] = {
    AgentRole.QA_ENGINEER: qa_execute,
    AgentRole.DEVOPS: devops_execute,
    AgentRole.RELEASE_MANAGER: release_execute,
}
