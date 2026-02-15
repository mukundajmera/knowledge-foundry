# Local Model Discovery API

## Overview

The Local Model Discovery API enables Knowledge Foundry to discover, manage, and chat with locally-running LLM models from Ollama and LMStudio. This provides cost-effective, privacy-focused alternatives to cloud-based LLMs.

## Features

- **Auto-Discovery**: Automatically detect running local providers (Ollama, LMStudio)
- **Model Management**: List, download, and delete Ollama models
- **Unified Chat Interface**: Single endpoint for chatting with any local model
- **Graceful Degradation**: Helpful error messages when providers are offline
- **Metadata Parsing**: Automatically extract model family, parameters, and quantization info

## Prerequisites

### Ollama Setup
1. Install Ollama from [https://ollama.ai](https://ollama.ai)
2. Start Ollama (default port: 11434)
3. Pull models: `ollama pull llama3:8b`

### LMStudio Setup
1. Install LM Studio from [https://lmstudio.ai](https://lmstudio.ai)
2. Load a model in LM Studio
3. Start the local server (default port: 1234)

## API Endpoints

### Discovery

#### GET `/api/models/local/discover`
Auto-detect running local providers and list their models.

**Response:**
```json
{
  "available_providers": ["ollama"],
  "ollama": {
    "provider": "ollama",
    "available": true,
    "models": [
      {
        "id": "llama3:8b-instruct-q4_0",
        "name": "llama3:8b-instruct-q4_0",
        "displayName": "Llama 3 8B Instruct (Q4_0)",
        "family": "llama",
        "parameters": "8B",
        "quantization": "Q4_0",
        "size": 4700000000,
        "digest": "sha256:...",
        "modified": "2024-02-15T10:30:00Z",
        "local": true
      }
    ],
    "count": 1
  },
  "lmstudio": {
    "provider": "lmstudio",
    "available": false,
    "error": "LMStudio not running on http://localhost:1234/v1",
    "models": [],
    "count": 0
  }
}
```

### Ollama Management

#### GET `/api/models/ollama/list`
List all available Ollama models.

**Response:** Same as `ollama` object in discovery response.

#### POST `/api/models/ollama/pull`
Download a new Ollama model.

**Request:**
```json
{
  "modelName": "llama3:8b"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully pulled model: llama3:8b",
  "model": "llama3:8b"
}
```

**Note:** Large models may take several minutes to download.

#### DELETE `/api/models/ollama/{model_name}`
Delete an Ollama model.

**Response:**
```json
{
  "success": true,
  "message": "Successfully deleted model: llama3:8b",
  "model": "llama3:8b"
}
```

### LMStudio Management

#### GET `/api/models/lmstudio/list`
List loaded LMStudio models.

**Response:** Similar format to Ollama list.

### Unified Chat

#### POST `/api/chat/local`
Chat with any local model using a unified interface.

**Request:**
```json
{
  "provider": "ollama",
  "modelId": "llama3:8b",
  "messages": [
    {
      "role": "user",
      "content": "What is 2+2?"
    }
  ],
  "stream": false,
  "options": {
    "temperature": 0.7,
    "maxTokens": 2048
  }
}
```

**Response:**
```json
{
  "success": true,
  "response": "2 + 2 = 4",
  "model": "llama3:8b",
  "provider": "ollama",
  "tokens": {
    "input": 10,
    "output": 6
  },
  "latency_ms": 150,
  "cost_usd": 0.0
}
```

**Supported Providers:**
- `ollama` - Ollama models
- `lmstudio` - LM Studio models

## Error Handling

### Provider Offline
When a provider is not running, the API returns status 200 with `available: false` and a helpful error message:

```json
{
  "provider": "ollama",
  "available": false,
  "error": "Ollama not running on http://localhost:11434",
  "models": [],
  "count": 0
}
```

### Invalid Model Name
Invalid model names return 400 Bad Request:

```json
{
  "detail": "Invalid model name format. Use alphanumeric characters, hyphens, colons, and dots."
}
```

### Timeout
Long-running operations (like model pull) may timeout. Adjust timeout settings in `.env`:

```bash
OLLAMA_TIMEOUT=300  # 5 minutes for model downloads
```

## Configuration

### Environment Variables

```bash
# Ollama Configuration
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=llama3
OLLAMA_TIMEOUT=120

# LMStudio Configuration
LMSTUDIO_HOST=localhost
LMSTUDIO_PORT=1234
LMSTUDIO_MODEL=
LMSTUDIO_TIMEOUT=60
```

## Performance

- **Discovery Latency**: <1s (p95) when providers are running
- **Model Listing**: <1s (p95)
- **Chat Latency**: Depends on model size and hardware
  - 7B models: 1-3s (p95) on modern hardware
  - 13B models: 3-8s (p95)
  - 70B models: 10-30s (p95)

## Security

- **Input Validation**: All inputs are validated using Pydantic models
- **No Credentials Required**: Local providers don't require API keys
- **Network Isolation**: Only communicates with localhost providers
- **Zero Cost**: Local inference has no cloud API costs

## Testing

### Run Unit Tests
```bash
pytest tests/unit/test_local_models.py -v
```

### Run Integration Tests
```bash
pytest tests/integration/test_local_models_api.py -v
```

### Manual Testing
```bash
# Start the API
uvicorn src.api.main:app --reload

# Discover providers
curl http://localhost:8000/api/models/local/discover

# List Ollama models
curl http://localhost:8000/api/models/ollama/list

# Chat with a model
curl -X POST http://localhost:8000/api/chat/local \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "modelId": "llama3:8b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Troubleshooting

### "Ollama not running"
- Verify Ollama is installed: `ollama --version`
- Start Ollama: `ollama serve`
- Check port: `curl http://localhost:11434/api/version`

### "LMStudio not running"
- Open LM Studio application
- Load a model
- Click "Start Server" in the local server tab
- Verify port: `curl http://localhost:1234/v1/models`

### Model pull timeout
- Increase timeout in configuration
- Check network connection
- Monitor download in Ollama: `ollama ps`

## Next Steps

- Frontend UI components for model discovery and selection
- Streaming chat responses (Server-Sent Events)
- Model comparison and benchmarking
- Automatic model recommendations based on task

## References

- [Ollama Documentation](https://github.com/ollama/ollama)
- [LM Studio](https://lmstudio.ai/)
- [Knowledge Foundry Architecture](../README.md)
