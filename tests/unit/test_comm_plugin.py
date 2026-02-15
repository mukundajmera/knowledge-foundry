"""Unit tests for Communication Plugin."""

import pytest
from src.plugins.communication import CommunicationPlugin

@pytest.mark.asyncio
async def test_comm_manifest():
    plugin = CommunicationPlugin()
    manifest = plugin.manifest()
    assert manifest.name == "communication"
    assert "send_message" in manifest.actions

@pytest.mark.asyncio
async def test_send_email_success():
    plugin = CommunicationPlugin()
    
    res = await plugin.execute("send_message", {
        "channel": "email",
        "recipient": "user@example.com",
        "content": "Work complete."
    })
    
    assert res.success is True
    assert res.data["status"] == "sent"
    assert res.data["message_id"] == "mock-msg-12345"

@pytest.mark.asyncio
async def test_missing_params():
    plugin = CommunicationPlugin()
    
    res = await plugin.execute("send_message", {"channel": "email"})
    
    assert res.success is False
    assert "Missing" in res.error
