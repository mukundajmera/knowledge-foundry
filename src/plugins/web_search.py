"""Knowledge Foundry — Web Search Plugin.

Provides web search capabilities (simulated for now, extensible to DuckDuckGo/Bing).
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.interfaces import Plugin, PluginManifest, PluginResult


class WebSearchPlugin(Plugin):
    """Plugin for performing web searches."""

    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="web_search",
            version="1.0.0",
            description="Searches the web for real-time information.",
            actions=["search"],
            permissions=["internet_access"],
        )

    async def execute(self, action: str, params: dict[str, Any]) -> PluginResult:
        if action != "search":
            return PluginResult(success=False, error=f"Unknown action: {action}")

        query = params.get("query")
        if not query:
            return PluginResult(success=False, error="Missing 'query' parameter")

        # Simulate network latency
        await asyncio.sleep(0.5)

        # In a real implementation, this would call DuckDuckGo or Bing API
        # For this PoC, we return a mock result
        mock_results = [
            {
                "title": f"Result for {query}",
                "url": "https://example.com/result1",
                "snippet": f"This is a simulated search result for the query: {query}. It contains relevant information."
            },
            {
                "title": "Wikipedia Entry",
                "url": "https://wikipedia.org/wiki/Search",
                "snippet": "Search is the act of looking for information..."
            }
        ]

        return PluginResult(success=True, data={"results": mock_results})
