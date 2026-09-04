"""Couche Agent Development Kit.

Le pipeline reste défini une seule fois, dans `greenlight.agents` et
`greenlight.tools`. Ce paquet ne le réimplémente pas : il l'expose sous la forme
que l'ADK attend, pour que le même code puisse tourner en bibliothèque locale ou
être déployé sur Vertex AI Agent Engine.
"""

from greenlight.adk.agents import build_clearance_agent
from greenlight.adk.runner import run_clearance_agent

__all__ = ["build_clearance_agent", "run_clearance_agent"]
