"""Knowledge Foundry — Communication Plugin.

Provides mock communication capabilities (Email, Slack) for agents to notify users.
"""

from __future__ import annotations

import structlog
from typing import Any

from src.core.interfaces import Plugin, PluginManifest, PluginResult

logger = structlog.get_logger(__name__)


class CommunicationPlugin(Plugin):
    """Plugin for sending notifications via various channels."""

    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="communication",
            version="1.0.0",
            description="Sends notifications via Email or Slack.",
            actions=["send_message"],
            permissions=["network_access"],
        )

    async def execute(self, action: str, params: dict[str, Any]) -> PluginResult:
        if action != "send_message":
            return PluginResult(success=False, error=f"Unknown action: {action}")

        channel = params.get("channel", "email")
        recipient = params.get("recipient")
        content = params.get("content")

        if not recipient or not content:
            return PluginResult(success=False, error="Missing 'recipient' or 'content'")

        # Mock simulation of sending
        logger.info(
            "Sending message",
            plugin="communication",
            channel=channel,
            recipient=recipient,
            content_preview=content[:50]
        )

        # In a real implementation, we would use SMTP or Slack API here.
        # For now, we return success with the simulated outcome.
        
        return PluginResult(
            success=True,
            data={
                "status": "sent",
                "message_id": "mock-msg-12345",
                "channel": channel,
                "recipient": recipient
            }
        )
