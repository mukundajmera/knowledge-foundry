"""Unit tests for local model discovery and management."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from src.api.routes.models import (
    parse_ollama_model_name,
    check_ollama_availability,
    check_lmstudio_availability,
    ProviderStatus,
    LocalModelInfo,
)


class TestOllamaModelParser:
    """Tests for Ollama model name parsing."""

    def test_parse_basic_model_name(self):
        """Test parsing basic model name with tag."""
        result = parse_ollama_model_name("llama3:8b-instruct-q4_0")
        
        assert result["family"] == "llama3"
        assert result["parameters"] == "8B"
        assert result["quantization"] == "Q4_0"
        assert "Llama3" in result["display_name"]
        assert "8B" in result["display_name"]
        assert "Q4_0" in result["display_name"]

    def test_parse_model_without_tag(self):
        """Test parsing model name without tag."""
        result = parse_ollama_model_name("llama2")
        
        assert result["family"] == "llama2"
        assert result["parameters"] is None
        assert result["quantization"] is None

    def test_parse_model_with_chat_suffix(self):
        """Test parsing model with chat suffix."""
        result = parse_ollama_model_name("mistral:7b-chat")
        
        assert result["family"] == "mistral"
        assert result["parameters"] == "7B"
        assert "Chat" in result["display_name"]

    def test_parse_model_with_instruct_suffix(self):
        """Test parsing model with instruct suffix."""
        result = parse_ollama_model_name("codellama:13b-instruct-q5_k_m")
        
        assert result["family"] == "codellama"
        assert result["parameters"] == "13B"
        assert result["quantization"] == "Q5_K_M"
        assert "Instruct" in result["display_name"]


class TestOllamaAvailability:
    """Tests for Ollama availability checking."""

    @pytest.mark.asyncio
    async def test_check_ollama_available(self):
        """Test Ollama availability when service is running."""
        # Mock responses
        version_response = Mock()
        version_response.status_code = 200
        
        tags_response = Mock()
        tags_response.status_code = 200
        tags_response.json.return_value = {
            "models": [
                {
                    "name": "llama3:8b",
                    "size": 4700000000,
                    "digest": "sha256:abc123",
                    "modified_at": "2024-02-15T10:00:00Z",
                }
            ]
        }
        
        # Mock httpx client
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get = AsyncMock(
                side_effect=[version_response, tags_response]
            )
            
            result = await check_ollama_availability()
            
            assert result.provider == "ollama"
            assert result.available is True
            assert result.error is None
            assert result.count == 1
            assert len(result.models) == 1
            assert result.models[0].name == "llama3:8b"

    @pytest.mark.asyncio
    async def test_check_ollama_timeout(self):
        """Test Ollama availability when service times out."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            
            result = await check_ollama_availability()
            
            assert result.provider == "ollama"
            assert result.available is False
            assert "timeout" in result.error.lower()
            assert result.count == 0
            assert len(result.models) == 0

    @pytest.mark.asyncio
    async def test_check_ollama_connection_error(self):
        """Test Ollama availability when service is not running."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            
            result = await check_ollama_availability()
            
            assert result.provider == "ollama"
            assert result.available is False
            assert "not running" in result.error.lower()


class TestLMStudioAvailability:
    """Tests for LMStudio availability checking."""

    @pytest.mark.asyncio
    async def test_check_lmstudio_available(self):
        """Test LMStudio availability when service is running."""
        # Mock response
        models_response = Mock()
        models_response.status_code = 200
        models_response.json.return_value = {
            "data": [
                {
                    "id": "llama-2-7b-chat.Q4_K_M.gguf",
                }
            ]
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get = AsyncMock(return_value=models_response)
            
            result = await check_lmstudio_availability()
            
            assert result.provider == "lmstudio"
            assert result.available is True
            assert result.error is None
            assert result.count == 1
            assert len(result.models) == 1
            assert "llama-2-7b-chat" in result.models[0].id

    @pytest.mark.asyncio
    async def test_check_lmstudio_timeout(self):
        """Test LMStudio availability when service times out."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            
            result = await check_lmstudio_availability()
            
            assert result.provider == "lmstudio"
            assert result.available is False
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_check_lmstudio_connection_error(self):
        """Test LMStudio availability when service is not running."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            
            result = await check_lmstudio_availability()
            
            assert result.provider == "lmstudio"
            assert result.available is False
            assert "not running" in result.error.lower()


class TestLocalModelInfo:
    """Tests for LocalModelInfo model."""

    def test_local_model_info_creation(self):
        """Test creating LocalModelInfo with all fields."""
        model = LocalModelInfo(
            id="llama3:8b",
            name="llama3:8b",
            displayName="Llama 3 8B",
            family="llama",
            parameters="8B",
            quantization="Q4_0",
            size=4700000000,
            digest="sha256:abc123",
            modified="2024-02-15T10:00:00Z",
            local=True,
        )
        
        assert model.id == "llama3:8b"
        assert model.display_name == "Llama 3 8B"
        assert model.family == "llama"
        assert model.local is True

    def test_local_model_info_minimal(self):
        """Test creating LocalModelInfo with minimal fields."""
        model = LocalModelInfo(
            id="test-model",
            name="test-model",
            displayName="Test Model",
        )
        
        assert model.id == "test-model"
        assert model.display_name == "Test Model"
        assert model.local is True
        assert model.family is None


class TestProviderStatus:
    """Tests for ProviderStatus model."""

    def test_provider_status_available(self):
        """Test ProviderStatus when provider is available."""
        model = LocalModelInfo(
            id="llama3:8b",
            name="llama3:8b",
            displayName="Llama 3 8B",
        )
        
        status = ProviderStatus(
            provider="ollama",
            available=True,
            models=[model],
            count=1,
        )
        
        assert status.provider == "ollama"
        assert status.available is True
        assert status.error is None
        assert len(status.models) == 1
        assert status.count == 1

    def test_provider_status_unavailable(self):
        """Test ProviderStatus when provider is unavailable."""
        status = ProviderStatus(
            provider="ollama",
            available=False,
            error="Connection refused",
        )
        
        assert status.provider == "ollama"
        assert status.available is False
        assert status.error == "Connection refused"
        assert len(status.models) == 0
        assert status.count == 0
