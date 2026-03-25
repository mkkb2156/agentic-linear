"""Worker service — DEPRECATED.

Agents are now dispatched directly by the gateway service.
This file is kept for backward compatibility. The gateway's
AgentDispatcher handles all agent execution as background tasks.

See: services/gateway/main.py and shared/dispatcher.py
"""
