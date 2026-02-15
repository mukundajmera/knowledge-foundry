# tests/e2e/test_api_e2e.py
import httpx
import pytest
import asyncio
import os

# Use env var or default
BASE_URL = os.getenv("API_URL", "http://localhost:8000")

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_health_check():
    """E2E: API is healthy"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_provider_listing():
    """E2E: Comparison of available providers"""
    # Endpoint not currently implemented, skipping
    pytest.skip("Provider listing endpoint not implemented")

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_simple_query():
    """E2E: Simple query execution"""
    # Skip if no API key in env (for local dev without keys)
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No API keys found in environment")
        
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        # Use a valid UUID for tenant_id to avoid 422
        valid_uuid = "2ae04715-72bc-4445-b4a0-e4f31568fbab"
        response = await client.post(
            "/v1/query",
            json={
                "query": "What is 2+2?", 
                "max_tokens": 50,
                "tenant_id": valid_uuid
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_error_handling():
    """E2E: Error handling"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        # 404
        r1 = await client.get("/v1/nonexistent")
        assert r1.status_code == 404
        
        # 422 Validation
        r2 = await client.post("/v1/query", json={})
        assert r2.status_code == 422
