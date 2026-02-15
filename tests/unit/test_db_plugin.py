"""Unit tests for Database Plugin."""

import pytest
from src.plugins.database import DatabasePlugin

@pytest.mark.asyncio
async def test_db_manifest():
    plugin = DatabasePlugin()
    manifest = plugin.manifest()
    assert manifest.name == "database"
    assert "query_sql" in manifest.actions

@pytest.mark.asyncio
async def test_db_query_success():
    plugin = DatabasePlugin() # defaults to :memory: with seed data
    
    res = await plugin.execute("query_sql", {"query": "SELECT * FROM users WHERE name = 'Alice'"})
    
    assert res.success is True
    assert len(res.data["results"]) == 1
    assert res.data["results"][0]["name"] == "Alice"
    assert res.data["results"][0]["email"] == "alice@example.com"

@pytest.mark.asyncio
async def test_db_security_readonly():
    plugin = DatabasePlugin()
    
    # Try DROP TABLE
    res = await plugin.execute("query_sql", {"query": "DROP TABLE users"})
    
    assert res.success is False
    assert "Security Violation" in res.error

@pytest.mark.asyncio
async def test_db_malformed_sql():
    plugin = DatabasePlugin()
    
    res = await plugin.execute("query_sql", {"query": "SELECT * FROM non_existent_table"})
    
    assert res.success is False
    assert "Database error" in res.error
