"""Integration tests for local model discovery API endpoints.

Tests the full API workflow including discovery, listing, and chat
with local LLM providers (Ollama and LMStudio).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.api.main import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)


class TestLocalDiscoveryAPI:
    """Integration tests for local provider discovery endpoint."""

    def test_discover_local_providers_both_offline(self, client):
        """Test discovery when both providers are offline."""
        # Mock both providers as unavailable
        with patch("src.api.routes.models.check_ollama_availability") as mock_ollama, \
             patch("src.api.routes.models.check_lmstudio_availability") as mock_lmstudio:
            
            from src.api.routes.models import ProviderStatus
            
            mock_ollama.return_value = ProviderStatus(
                provider="ollama",
                available=False,
                error="Ollama not running",
            )
            mock_lmstudio.return_value = ProviderStatus(
                provider="lmstudio",
                available=False,
                error="LMStudio not running",
            )
            
            response = client.get("/api/models/local/discover")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["available_providers"] == []
            assert data["ollama"]["available"] is False
            assert data["lmstudio"]["available"] is False
            assert "not running" in data["ollama"]["error"].lower()

    def test_discover_local_providers_ollama_online(self, client):
        """Test discovery when Ollama is online."""
        with patch("src.api.routes.models.check_ollama_availability") as mock_ollama, \
             patch("src.api.routes.models.check_lmstudio_availability") as mock_lmstudio:
            
            from src.api.routes.models import ProviderStatus, LocalModelInfo
            
            mock_ollama.return_value = ProviderStatus(
                provider="ollama",
                available=True,
                models=[
                    LocalModelInfo(
                        id="llama3:8b",
                        name="llama3:8b",
                        displayName="Llama 3 8B",
                        local=True,
                    )
                ],
                count=1,
            )
            mock_lmstudio.return_value = ProviderStatus(
                provider="lmstudio",
                available=False,
                error="LMStudio not running",
            )
            
            response = client.get("/api/models/local/discover")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "ollama" in data["available_providers"]
            assert "lmstudio" not in data["available_providers"]
            assert data["ollama"]["available"] is True
            assert data["ollama"]["count"] == 1


class TestOllamaAPI:
    """Integration tests for Ollama-specific endpoints."""

    def test_list_ollama_models_unavailable(self, client):
        """Test listing Ollama models when service is unavailable."""
        with patch("src.api.routes.models.check_ollama_availability") as mock_ollama:
            from src.api.routes.models import ProviderStatus
            
            mock_ollama.return_value = ProviderStatus(
                provider="ollama",
                available=False,
                error="Connection refused",
            )
            
            response = client.get("/api/models/ollama/list")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["provider"] == "ollama"
            assert data["available"] is False
            assert data["count"] == 0

    def test_list_ollama_models_available(self, client):
        """Test listing Ollama models when service is available."""
        with patch("src.api.routes.models.check_ollama_availability") as mock_ollama:
            from src.api.routes.models import ProviderStatus, LocalModelInfo
            
            mock_ollama.return_value = ProviderStatus(
                provider="ollama",
                available=True,
                models=[
                    LocalModelInfo(
                        id="llama3:8b",
                        name="llama3:8b",
                        displayName="Llama 3 8B",
                        family="llama",
                        parameters="8B",
                        size=4700000000,
                        local=True,
                    ),
                    LocalModelInfo(
                        id="mistral:7b",
                        name="mistral:7b",
                        displayName="Mistral 7B",
                        family="mistral",
                        parameters="7B",
                        size=4100000000,
                        local=True,
                    ),
                ],
                count=2,
            )
            
            response = client.get("/api/models/ollama/list")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["provider"] == "ollama"
            assert data["available"] is True
            assert data["count"] == 2
            assert len(data["models"]) == 2

    def test_pull_ollama_model_invalid_name(self, client):
        """Test pulling Ollama model with invalid name."""
        response = client.post(
            "/api/models/ollama/pull",
            json={"modelName": "invalid/model@name"},
        )
        
        assert response.status_code == 400
        assert "Invalid model name" in response.json()["detail"]

    def test_delete_ollama_model_service_unavailable(self, client):
        """Test deleting Ollama model when service is unavailable."""
        with patch("httpx.AsyncClient") as mock_client:
            import httpx
            
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.delete = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            
            response = client.delete("/api/models/ollama/llama3:8b")
            
            assert response.status_code == 503
            assert "not running" in response.json()["detail"].lower()


class TestLMStudioAPI:
    """Integration tests for LMStudio-specific endpoints."""

    def test_list_lmstudio_models_unavailable(self, client):
        """Test listing LMStudio models when service is unavailable."""
        with patch("src.api.routes.models.check_lmstudio_availability") as mock_lmstudio:
            from src.api.routes.models import ProviderStatus
            
            mock_lmstudio.return_value = ProviderStatus(
                provider="lmstudio",
                available=False,
                error="Connection refused",
            )
            
            response = client.get("/api/models/lmstudio/list")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["provider"] == "lmstudio"
            assert data["available"] is False
            assert data["count"] == 0

    def test_list_lmstudio_models_available(self, client):
        """Test listing LMStudio models when service is available."""
        with patch("src.api.routes.models.check_lmstudio_availability") as mock_lmstudio:
            from src.api.routes.models import ProviderStatus, LocalModelInfo
            
            mock_lmstudio.return_value = ProviderStatus(
                provider="lmstudio",
                available=True,
                models=[
                    LocalModelInfo(
                        id="llama-2-7b-chat.Q4_K_M.gguf",
                        name="llama-2-7b-chat.Q4_K_M.gguf",
                        displayName="Llama 2 7B Chat (Q4_K_M)",
                        family="llama",
                        parameters="7B",
                        quantization="Q4_K_M",
                        local=True,
                    ),
                ],
                count=1,
            )
            
            response = client.get("/api/models/lmstudio/list")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["provider"] == "lmstudio"
            assert data["available"] is True
            assert data["count"] == 1


class TestLocalChatAPI:
    """Integration tests for unified local chat endpoint."""

    def test_chat_invalid_provider(self, client):
        """Test chat with invalid provider name."""
        response = client.post(
            "/api/models/chat/local",
            json={
                "provider": "invalid_provider",
                "modelId": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        
        assert response.status_code == 400
        assert "Unsupported provider" in response.json()["detail"]

    def test_chat_with_ollama_success(self, client):
        """Test successful chat with Ollama provider."""
        with patch("src.api.routes.models.OllamaProvider") as mock_provider_class:
            # Mock the provider instance
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            
            # Mock the response
            from src.core.interfaces import LLMResponse, ModelTier
            mock_provider.generate = AsyncMock(
                return_value=LLMResponse(
                    text="Hello! How can I help you?",
                    model="llama3:8b",
                    tier=ModelTier.SONNET,
                    confidence=0.9,
                    input_tokens=10,
                    output_tokens=8,
                    latency_ms=150,
                    cost_usd=0.0,
                )
            )
            
            response = client.post(
                "/api/models/chat/local",
                json={
                    "provider": "ollama",
                    "modelId": "llama3:8b",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["provider"] == "ollama"
            assert data["model"] == "llama3:8b"
            assert "response" in data
            assert data["tokens"]["input"] == 10
            assert data["tokens"]["output"] == 8

    def test_chat_with_lmstudio_success(self, client):
        """Test successful chat with LMStudio provider."""
        with patch("src.api.routes.models.LMStudioProvider") as mock_provider_class:
            # Mock the provider instance
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            
            # Mock the response
            from src.core.interfaces import LLMResponse, ModelTier
            mock_provider.generate = AsyncMock(
                return_value=LLMResponse(
                    text="Hi there!",
                    model="llama-2-7b-chat.Q4_K_M.gguf",
                    tier=ModelTier.SONNET,
                    confidence=0.85,
                    input_tokens=8,
                    output_tokens=4,
                    latency_ms=120,
                    cost_usd=0.0,
                )
            )
            
            response = client.post(
                "/api/models/chat/local",
                json={
                    "provider": "lmstudio",
                    "modelId": "llama-2-7b-chat.Q4_K_M.gguf",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["provider"] == "lmstudio"
            assert "response" in data

    def test_chat_with_system_prompt(self, client):
        """Test chat with system prompt included."""
        with patch("src.api.routes.models.OllamaProvider") as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            
            from src.core.interfaces import LLMResponse, ModelTier
            mock_provider.generate = AsyncMock(
                return_value=LLMResponse(
                    text="2 + 2 = 4",
                    model="llama3:8b",
                    tier=ModelTier.SONNET,
                    confidence=0.95,
                    input_tokens=15,
                    output_tokens=6,
                    latency_ms=100,
                    cost_usd=0.0,
                )
            )
            
            response = client.post(
                "/api/models/chat/local",
                json={
                    "provider": "ollama",
                    "modelId": "llama3:8b",
                    "messages": [
                        {"role": "system", "content": "You are a helpful math assistant."},
                        {"role": "user", "content": "What is 2 + 2?"},
                    ],
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestCrossProviderIntegration:
    """Integration tests across multiple providers."""

    def test_discover_and_chat_workflow(self, client):
        """Test full workflow: discover -> list -> chat."""
        # Step 1: Discover providers
        with patch("src.api.routes.models.check_ollama_availability") as mock_ollama, \
             patch("src.api.routes.models.check_lmstudio_availability") as mock_lmstudio:
            
            from src.api.routes.models import ProviderStatus, LocalModelInfo
            
            mock_ollama.return_value = ProviderStatus(
                provider="ollama",
                available=True,
                models=[
                    LocalModelInfo(
                        id="llama3:8b",
                        name="llama3:8b",
                        displayName="Llama 3 8B",
                        local=True,
                    )
                ],
                count=1,
            )
            mock_lmstudio.return_value = ProviderStatus(
                provider="lmstudio",
                available=False,
                error="LMStudio not running",
            )
            
            discovery_response = client.get("/api/models/local/discover")
            assert discovery_response.status_code == 200
            discovery_data = discovery_response.json()
            assert "ollama" in discovery_data["available_providers"]
        
        # Step 2: List Ollama models
        with patch("src.api.routes.models.check_ollama_availability") as mock_ollama:
            from src.api.routes.models import ProviderStatus, LocalModelInfo
            
            mock_ollama.return_value = ProviderStatus(
                provider="ollama",
                available=True,
                models=[
                    LocalModelInfo(
                        id="llama3:8b",
                        name="llama3:8b",
                        displayName="Llama 3 8B",
                        local=True,
                    )
                ],
                count=1,
            )
            
            list_response = client.get("/api/models/ollama/list")
            assert list_response.status_code == 200
            list_data = list_response.json()
            assert list_data["count"] == 1
            model_id = list_data["models"][0]["id"]
        
        # Step 3: Chat with discovered model
        with patch("src.api.routes.models.OllamaProvider") as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            
            from src.core.interfaces import LLMResponse, ModelTier
            mock_provider.generate = AsyncMock(
                return_value=LLMResponse(
                    text="Test response",
                    model=model_id,
                    tier=ModelTier.SONNET,
                    confidence=0.9,
                    input_tokens=10,
                    output_tokens=5,
                    latency_ms=100,
                    cost_usd=0.0,
                )
            )
            
            chat_response = client.post(
                "/api/models/chat/local",
                json={
                    "provider": "ollama",
                    "modelId": model_id,
                    "messages": [{"role": "user", "content": "Test"}],
                },
            )
            
            assert chat_response.status_code == 200
            chat_data = chat_response.json()
            assert chat_data["success"] is True
            assert chat_data["model"] == model_id
