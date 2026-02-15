"""Knowledge Foundry — Local Model Discovery Routes.

API endpoints for discovering and managing local LLM providers (Ollama, LMStudio).
Implements auto-discovery, model listing, and unified chat interface.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.core.config import get_settings
from src.llm.providers import LMStudioProvider, OllamaProvider

router = APIRouter(prefix="/api/models", tags=["models"])
logger = logging.getLogger(__name__)


# =============================================================
# REQUEST/RESPONSE MODELS
# =============================================================


class LocalModelInfo(BaseModel):
    """Information about a local LLM model."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    display_name: str = Field(alias="displayName")
    family: str | None = None
    parameters: str | None = None
    quantization: str | None = None
    size: int | None = None
    digest: str | None = None
    modified: str | None = None
    local: bool = True


class ProviderStatus(BaseModel):
    """Status of a local LLM provider."""

    provider: str
    available: bool
    error: str | None = None
    models: list[LocalModelInfo] = Field(default_factory=list)
    count: int = 0


class LocalDiscoveryResponse(BaseModel):
    """Response from local provider discovery."""

    available_providers: list[str] = Field(default_factory=list)
    ollama: ProviderStatus
    lmstudio: ProviderStatus


class PullModelRequest(BaseModel):
    """Request to pull/download a new Ollama model."""

    model_config = ConfigDict(populate_by_name=True)

    model_name: str = Field(alias="modelName")


class ChatMessage(BaseModel):
    """Chat message for local model chat."""

    role: str
    content: str


class LocalChatRequest(BaseModel):
    """Request for chatting with a local model."""

    model_config = ConfigDict(populate_by_name=True)

    provider: str  # "ollama" or "lmstudio"
    model_id: str = Field(alias="modelId")
    messages: list[ChatMessage]
    stream: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


# =============================================================
# HELPER FUNCTIONS
# =============================================================


def parse_ollama_model_name(model_name: str) -> dict[str, str | None]:
    """Parse Ollama model name to extract metadata.
    
    Example: llama3:8b-instruct-q4_0 -> 
        family=llama, parameters=8B, quantization=Q4_0
    """
    parts = model_name.split(":")
    base_name = parts[0] if parts else model_name
    
    tag = parts[1] if len(parts) > 1 else ""
    
    # Extract family (first part before numbers)
    family = base_name.split("-")[0] if "-" in base_name else base_name
    
    # Extract parameters (e.g., 7b, 13b, 70b)
    parameters = None
    for part in tag.split("-"):
        if part and part[0].isdigit() and part[-1].lower() == "b":
            parameters = part.upper()
            break
    
    # Extract quantization (e.g., Q4_0, Q5_K_M)
    quantization = None
    for part in tag.split("-"):
        if part.upper().startswith("Q"):
            quantization = part.upper()
            break
    
    # Create display name
    display_parts = [family.title()]
    if parameters:
        display_parts.append(parameters)
    if "instruct" in tag.lower():
        display_parts.append("Instruct")
    if "chat" in tag.lower():
        display_parts.append("Chat")
    if quantization:
        display_parts.append(f"({quantization})")
    
    display_name = " ".join(display_parts)
    
    return {
        "family": family,
        "parameters": parameters,
        "quantization": quantization,
        "display_name": display_name,
    }


async def check_ollama_availability() -> ProviderStatus:
    """Check if Ollama is running and list available models."""
    settings = get_settings()
    base_url = settings.ollama.base_url
    timeout = settings.ollama.timeout
    
    try:
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            # Check health
            version_resp = await client.get(f"{base_url}/api/version")
            if version_resp.status_code != 200:
                return ProviderStatus(
                    provider="ollama",
                    available=False,
                    error="Ollama API returned non-200 status",
                )
            
            # List models
            tags_resp = await client.get(f"{base_url}/api/tags")
            tags_resp.raise_for_status()
            data = tags_resp.json()
            
            models_list = []
            for model_data in data.get("models", []):
                model_name = model_data.get("name", "")
                parsed = parse_ollama_model_name(model_name)
                
                models_list.append(
                    LocalModelInfo(
                        id=model_name,
                        name=model_name,
                        displayName=parsed["display_name"],
                        family=parsed["family"],
                        parameters=parsed["parameters"],
                        quantization=parsed["quantization"],
                        size=model_data.get("size"),
                        digest=model_data.get("digest"),
                        modified=model_data.get("modified_at"),
                        local=True,
                    )
                )
            
            return ProviderStatus(
                provider="ollama",
                available=True,
                models=models_list,
                count=len(models_list),
            )
    
    except httpx.TimeoutException:
        return ProviderStatus(
            provider="ollama",
            available=False,
            error="Ollama not responding (timeout)",
        )
    except httpx.ConnectError:
        return ProviderStatus(
            provider="ollama",
            available=False,
            error=f"Ollama not running on {base_url}",
        )
    except Exception as e:
        logger.error(f"Ollama discovery failed: {e}")
        return ProviderStatus(
            provider="ollama",
            available=False,
            error="Unexpected error during discovery",
        )


async def check_lmstudio_availability() -> ProviderStatus:
    """Check if LMStudio is running and list loaded models."""
    settings = get_settings()
    base_url = settings.lmstudio.base_url
    timeout = settings.lmstudio.timeout
    
    try:
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            # Check health and list models (OpenAI-compatible)
            models_resp = await client.get(f"{base_url}/models")
            models_resp.raise_for_status()
            data = models_resp.json()
            
            models_list = []
            for model_data in data.get("data", []):
                model_id = model_data.get("id", "")
                
                # Parse GGUF filename if present
                # e.g., llama-2-7b-chat.Q4_K_M.gguf -> Llama 2 7B Chat (Q4_K_M)
                display_name = model_id
                family = None
                parameters = None
                quantization = None
                
                if ".gguf" in model_id.lower():
                    parts = model_id.replace(".gguf", "").split(".")
                    base = parts[0] if parts else model_id
                    quant = parts[1] if len(parts) > 1 else None
                    
                    # Build display name from base
                    name_parts = base.replace("-", " ").split()
                    display_parts = []
                    for part in name_parts:
                        if part and part[0].isdigit() and part[-1].lower() == "b":
                            parameters = part.upper()
                            display_parts.append(parameters)
                        else:
                            display_parts.append(part.title())
                    
                    if quant:
                        quantization = quant.upper()
                        display_parts.append(f"({quantization})")
                    
                    display_name = " ".join(display_parts)
                    family = name_parts[0] if name_parts else None
                
                models_list.append(
                    LocalModelInfo(
                        id=model_id,
                        name=model_id,
                        displayName=display_name,
                        family=family,
                        parameters=parameters,
                        quantization=quantization,
                        local=True,
                    )
                )
            
            return ProviderStatus(
                provider="lmstudio",
                available=True,
                models=models_list,
                count=len(models_list),
            )
    
    except httpx.TimeoutException:
        return ProviderStatus(
            provider="lmstudio",
            available=False,
            error="LMStudio not responding (timeout)",
        )
    except httpx.ConnectError:
        return ProviderStatus(
            provider="lmstudio",
            available=False,
            error=f"LMStudio not running on {base_url}",
        )
    except Exception as e:
        logger.error(f"LMStudio discovery failed: {e}")
        return ProviderStatus(
            provider="lmstudio",
            available=False,
            error="Unexpected error during discovery",
        )


# =============================================================
# ROUTES
# =============================================================


@router.get("/local/discover", response_model=LocalDiscoveryResponse)
async def discover_local_providers() -> LocalDiscoveryResponse:
    """Auto-detect running local LLM providers (Ollama, LMStudio).
    
    Checks both Ollama (port 11434) and LMStudio (port 1234) in parallel
    with 5s timeout. Returns available providers with their models.
    
    Returns:
        LocalDiscoveryResponse with status of each provider.
    """
    # Run discovery in parallel
    ollama_task = check_ollama_availability()
    lmstudio_task = check_lmstudio_availability()
    
    ollama_status, lmstudio_status = await asyncio.gather(
        ollama_task, lmstudio_task
    )
    
    available_providers = []
    if ollama_status.available:
        available_providers.append("ollama")
    if lmstudio_status.available:
        available_providers.append("lmstudio")
    
    return LocalDiscoveryResponse(
        available_providers=available_providers,
        ollama=ollama_status,
        lmstudio=lmstudio_status,
    )


@router.get("/ollama/list", response_model=ProviderStatus)
async def list_ollama_models() -> ProviderStatus:
    """List all available Ollama models.
    
    Returns:
        ProviderStatus with Ollama models and metadata.
    """
    return await check_ollama_availability()


@router.post("/ollama/pull")
async def pull_ollama_model(request: PullModelRequest) -> dict[str, Any]:
    """Pull/download a new Ollama model.
    
    Args:
        request: PullModelRequest with model_name to download.
    
    Returns:
        Status message indicating pull started.
    
    Note:
        This endpoint initiates the pull. For streaming progress,
        use Server-Sent Events (SSE) in a future implementation.
    """
    settings = get_settings()
    base_url = settings.ollama.base_url
    # Use a longer timeout for model pulls (they can take several minutes)
    pull_timeout = min(settings.ollama.timeout * 3, 600.0)  # 3x normal timeout, max 10min
    
    # Validate model name format
    model_name = request.model_name
    if not model_name or not all(c.isalnum() or c in ":-_." for c in model_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid model name format. Use alphanumeric characters, hyphens, colons, and dots.",
        )
    
    try:
        async with httpx.AsyncClient(timeout=pull_timeout) as client:
            # Initiate pull (non-streaming for now)
            pull_resp = await client.post(
                f"{base_url}/api/pull",
                json={"name": model_name, "stream": False},
            )
            pull_resp.raise_for_status()
            
            return {
                "success": True,
                "message": f"Successfully pulled model: {model_name}",
                "model": model_name,
            }
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ollama pull failed: {e.response.text}",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Model pull timed out. Large models may take several minutes.",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Ollama not running. Please start Ollama and try again.",
        )


@router.delete("/ollama/{model_name}")
async def delete_ollama_model(model_name: str) -> dict[str, Any]:
    """Delete an Ollama model.
    
    Args:
        model_name: Name of the model to delete.
    
    Returns:
        Status message indicating deletion success.
    """
    settings = get_settings()
    base_url = settings.ollama.base_url
    timeout = settings.ollama.timeout
    
    try:
        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            delete_resp = await client.delete(
                f"{base_url}/api/delete",
                json={"name": model_name},
            )
            delete_resp.raise_for_status()
            
            return {
                "success": True,
                "message": f"Successfully deleted model: {model_name}",
                "model": model_name,
            }
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ollama delete failed: {e.response.text}",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Ollama not running. Please start Ollama and try again.",
        )


@router.get("/lmstudio/list", response_model=ProviderStatus)
async def list_lmstudio_models() -> ProviderStatus:
    """List loaded LMStudio models.
    
    Returns:
        ProviderStatus with LMStudio models.
    """
    return await check_lmstudio_availability()


@router.post("/chat/local")
async def chat_with_local_model(
    request: LocalChatRequest,
) -> dict[str, Any]:
    """Chat with a local model (unified endpoint for Ollama and LMStudio).
    
    Args:
        request: LocalChatRequest with provider, model, messages, and options.
    
    Returns:
        Chat response with generated text and metadata.
    """
    provider_name = request.provider.lower()
    
    # Validate provider
    if provider_name not in ["ollama", "lmstudio"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: {provider_name}. Use 'ollama' or 'lmstudio'.",
        )
    
    # Build prompt from messages
    prompt_parts = []
    system_prompt = None
    for msg in request.messages:
        if msg.role == "system":
            system_prompt = msg.content
        elif msg.role == "user":
            prompt_parts.append(msg.content)
        elif msg.role == "assistant":
            # Include assistant messages for context
            prompt_parts.append(f"Assistant: {msg.content}")
    
    prompt = "\n".join(prompt_parts)
    
    # Get options
    temperature = request.options.get("temperature", 0.7)
    max_tokens = request.options.get("maxTokens", 2048)
    
    try:
        # Create provider instance
        if provider_name == "ollama":
            provider = OllamaProvider()
        else:  # lmstudio
            provider = LMStudioProvider()
        
        # Import LLMConfig
        from src.core.interfaces import LLMConfig, ModelTier
        
        config = LLMConfig(
            model=request.model_id,
            tier=ModelTier.SONNET,  # Default tier
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )
        
        # Generate response
        response = await provider.generate(prompt, config)
        
        return {
            "success": True,
            "response": response.text,
            "model": response.model,
            "provider": provider_name,
            "tokens": {
                "input": response.input_tokens,
                "output": response.output_tokens,
            },
            "latency_ms": response.latency_ms,
            "cost_usd": response.cost_usd,
        }
    
    except Exception as e:
        logger.error(f"Local chat failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chat with {provider_name} failed: {str(e)}",
        )
