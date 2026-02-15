CONTEXT & STRATEGIC DIRECTIVE
You are the Lead AI Engineer for Knowledge Foundry, a production enterprise RAG platform. Your mission is to implement three critical features that will position Knowledge Foundry as a market leader:

Local LLM Provider Discovery (Ollama + LMStudio)

MCP Protocol Integration (Atlassian: Confluence, Jira, Bitbucket)

Full-Stack Testing Infrastructure (E2E user workflow validation)

Repository Architecture (assumed based on standard Next.js + FastAPI stack):

text
knowledge-foundry/
├── frontend/                 # Next.js 14+ (App Router)
│   ├── app/                  # Routes & pages
│   ├── components/           # React components
│   ├── lib/                  # Frontend utilities
│   └── types/                # TypeScript interfaces
├── backend/                  # FastAPI + Python 3.11+
│   ├── api/                  # API routes
│   ├── core/                 # Business logic
│   ├── models/               # Data models (Pydantic)
│   ├── services/             # External integrations
│   └── tests/                # Pytest test suite
├── config/                   # Configuration files
└── docker-compose.yml        # Multi-container orchestration
High-Performance Requirements:

Zero breaking changes to existing functionality

<500ms p95 latency for all new endpoints

>90% test coverage with pytest + Playwright

Production-ready security (input validation, auth, rate limiting)

EU AI Act compliant (audit logging, user consent)

🎯 FEATURE 1: LOCAL LLM PROVIDER DISCOVERY & INTEGRATION
OBJECTIVE
Enable Knowledge Foundry users to discover, select, and use locally-running LLM models from Ollama and LMStudio without cloud dependencies, reducing cost and improving privacy.

TECHNICAL REQUIREMENTS
Ollama Integration (Port: 11434):

Health Check: GET http://localhost:11434/api/version (5s timeout)

Model Listing: GET http://localhost:11434/api/tags → Returns available models with metadata (name, size, digest, modified)

Model Operations: Pull (POST /api/pull), Delete (DELETE /api/delete), Info (POST /api/show)

Streaming Chat: POST /api/chat with stream: true → Server-Sent Events (SSE)

Model Format: Handle quantization levels (Q4_0, Q5_K_M, etc.) and parameter sizes (7B, 13B, 70B)

LMStudio Integration (Port: 1234, OpenAI-compatible):

Health Check: GET http://localhost:1234/v1/models (5s timeout)

Model Listing: OpenAI-compatible /v1/models endpoint

Streaming Chat: OpenAI SDK with baseURL: "http://localhost:1234/v1"

Model Display: Parse GGUF filenames (e.g., llama-2-7b-chat.Q4_K_M.gguf → "Llama 2 7B Chat (Q4_K_M)")

IMPLEMENTATION SPECIFICATIONS
Backend API Routes (backend/api/models/):

GET /api/models/local/discover - Auto-detect running local providers

Check Ollama (port 11434) and LMStudio (port 1234) in parallel with 5s timeout

Return: {available_providers: ["ollama", "lmstudio"], ollama: {...}, lmstudio: {...}}

Error handling: Return empty arrays + helpful setup instructions if neither detected

GET /api/models/ollama/list - List Ollama models

Response format:

json
{
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
}
POST /api/models/ollama/pull - Download new Ollama model

Request: {modelName: "llama3:8b"}

Streaming progress updates via SSE

Validation: Model name format (alphanumeric + hyphens, optional tag)

DELETE /api/models/ollama/{model_name} - Remove Ollama model

Authorization: Require admin role

Validation: Prevent deletion of currently-active model

GET /api/models/lmstudio/list - List loaded LMStudio models

Use OpenAI SDK: openai.models.list() with custom baseURL

Response format similar to Ollama (normalize to common interface)

POST /api/chat/local - Chat with local model (unified endpoint)

Request:

json
{
  "provider": "ollama" | "lmstudio",
  "modelId": "llama3:8b",
  "messages": [{"role": "user", "content": "..."}],
  "stream": true,
  "options": {"temperature": 0.7, "maxTokens": 2048}
}
SSE streaming for both providers

Error handling: Graceful fallback to cloud models if local provider crashes

Frontend UI Components (frontend/components/ModelSelector/):

LocalProviderDiscovery.tsx - Auto-discovery UI

Auto-refresh every 30 seconds

Visual indicators: 🟢 Running / 🔴 Not Detected

Setup instructions modal for each provider (installation steps)

TypeScript interface: LocalProvider { name: string; available: boolean; port: number; models: Model[] }

OllamaModelList.tsx - Ollama model manager

Grid view with model cards (image, name, size, quantization badge)

Pull new model: Input field + "Download" button → Progress bar with % + speed (MB/s)

Delete model: Confirmation dialog with warning

Model details on click: Parameters, last modified, disk usage

LMStudioModelList.tsx - LMStudio loaded models

Similar card layout

Read-only (models managed in LMStudio app)

"Open LMStudio" button if not running

UnifiedModelSelector.tsx - Combined model picker

Tabs: Cloud Models | Ollama | LMStudio

Grouped by provider + sorted by recency

Search/filter: By name, parameter size, quantization

Selection persistence: localStorage selectedModel: {provider, modelId}

Configuration & Environment:

backend/.env: OLLAMA_BASE_URL=http://localhost:11434, LMSTUDIO_BASE_URL=http://localhost:1234/v1

Frontend: NEXT_PUBLIC_ALLOW_LOCAL_MODELS=true (feature flag)

CORS: Allow localhost origins for development

Error Handling Patterns:

python
# Backend example
try:
    response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
    response.raise_for_status()
    models = response.json()
except httpx.TimeoutException:
    return {"available": False, "error": "Ollama not responding (timeout)", "models": []}
except httpx.ConnectError:
    return {"available": False, "error": "Ollama not running on port 11434", "models": []}
except Exception as e:
    logger.error(f"Ollama discovery failed: {e}")
    return {"available": False, "error": "Unexpected error", "models": []}
🔌 FEATURE 2: MCP (MODEL CONTEXT PROTOCOL) INTEGRATION
OBJECTIVE
Enable Knowledge Foundry to securely access Atlassian tools (Confluence, Jira, Bitbucket) using the Model Context Protocol standard, allowing AI agents to read company knowledge bases and development data.

AUTHENTICATION STRATEGIES
Confluence (Session-Based):

Why: No API token required; users provide session cookies from authenticated browser

Cookies needed: JSESSIONID + cloud.session.token

User workflow:

User logs into Confluence in browser

Opens DevTools → Application → Cookies

Copies JSESSIONID and cloud.session.token values

Pastes into Knowledge Foundry UI (encrypted storage)

API calls: Include cookies in headers: Cookie: JSESSIONID=...; cloud.session.token=...

Session duration: Typically 12-24 hours; requires re-authentication after expiry

Security: Cookies encrypted at rest (AES-256), never logged

Jira & Bitbucket (Token-Based):

Why: Programmatic access via Personal Access Tokens (PAT) or API tokens

Token types:

Jira Cloud: API Token from https://id.atlassian.com/manage-profile/security/api-tokens

Bitbucket Cloud: App Password from https://bitbucket.org/account/settings/app-passwords/

Storage: Encrypted in database with per-user keys

API calls: Authorization: Bearer {token} or Basic {base64(username:token)}

MCP SERVER ARCHITECTURE
What is MCP?
Model Context Protocol is a standardized interface for AI assistants to interact with external tools and data sources. It defines:

Tools: Functions the AI can call (e.g., confluence_search_pages, jira_get_issue)

Resources: Data sources (e.g., Confluence spaces, Jira projects)

Prompts: Pre-defined interaction templates

Knowledge Foundry MCP Implementation:

MCP Server (backend/mcp/servers/):

Python-based MCP server using @modelcontextprotocol/sdk

Runs as separate process, communicates via stdio or HTTP

One server per tool: confluence_server.py, jira_server.py, bitbucket_server.py

MCP Client (backend/services/mcp_client.py):

FastAPI integration that calls MCP servers

Tool discovery and invocation

Result caching (Redis) to reduce API calls

Confluence MCP Tools:

python
# backend/mcp/servers/confluence_server.py

CONFLUENCE_TOOLS = [
    {
        "name": "confluence_set_credentials",
        "description": "Authenticate with Confluence using session cookies from browser",
        "input_schema": {
            "type": "object",
            "properties": {
                "base_url": {"type": "string", "description": "Confluence URL (e.g., https://company.atlassian.net/wiki)"},
                "session_id": {"type": "string", "description": "JSESSIONID cookie value"},
                "session_token": {"type": "string", "description": "cloud.session.token cookie value"}
            },
            "required": ["base_url", "session_id", "session_token"]
        }
    },
    {
        "name": "confluence_search_pages",
        "description": "Search Confluence pages using CQL (Confluence Query Language)",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (CQL syntax: text ~ \"keyword\")"},
                "space_key": {"type": "string", "description": "Filter by space (optional)"},
                "limit": {"type": "integer", "default": 10, "description": "Max results (1-100)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "confluence_get_page_content",
        "description": "Retrieve full content of a Confluence page",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Confluence page ID"}
            },
            "required": ["page_id"]
        }
    },
    {
        "name": "confluence_list_spaces",
        "description": "List all accessible Confluence spaces",
        "input_schema": {"type": "object", "properties": {}}
    }
]

# Example implementation
async def confluence_search_pages(query: str, space_key: str = None, limit: int = 10):
    """Search Confluence using CQL"""
    cql = f'text ~ "{query}"'
    if space_key:
        cql += f' AND space = {space_key}'
    
    headers = {
        "Cookie": f"JSESSIONID={session_id}; cloud.session.token={session_token}",
        "Content-Type": "application/json"
    }
    
    response = await httpx.get(
        f"{base_url}/rest/api/content/search",
        params={"cql": cql, "limit": limit, "expand": "space,version"},
        headers=headers,
        timeout=10.0
    )
    
    if response.status_code == 401:
        raise AuthenticationError("Session expired. Re-authenticate with Confluence.")
    
    response.raise_for_status()
    data = response.json()
    
    return {
        "results": [
            {
                "id": page["id"],
                "title": page["title"],
                "space": page["space"]["name"],
                "url": f"{base_url}{page['_links']['webui']}",
                "lastModified": page["version"]["when"]
            }
            for page in data["results"]
        ],
        "total": data["size"]
    }
Jira MCP Tools (Token-Based):

python
JIRA_TOOLS = [
    {
        "name": "jira_set_credentials",
        "description": "Authenticate with Jira using API token",
        "input_schema": {
            "base_url": {"type": "string"},
            "email": {"type": "string"},
            "api_token": {"type": "string"}
        }
    },
    {
        "name": "jira_search_issues",
        "description": "Search Jira issues using JQL",
        "input_schema": {
            "jql": {"type": "string", "description": "JQL query (e.g., project = KF AND status = Open)"},
            "limit": {"type": "integer", "default": 50}
        }
    },
    {
        "name": "jira_get_issue",
        "description": "Get full details of a Jira issue",
        "input_schema": {"issue_key": {"type": "string", "description": "Issue key (e.g., KF-123)"}}
    },
    {
        "name": "jira_create_issue",
        "description": "Create a new Jira issue",
        "input_schema": {
            "project_key": {"type": "string"},
            "issue_type": {"type": "string", "enum": ["Story", "Task", "Bug"]},
            "summary": {"type": "string"},
            "description": {"type": "string"}
        }
    }
]

# Authentication
headers = {
    "Authorization": f"Basic {base64.b64encode(f'{email}:{api_token}'.encode()).decode()}",
    "Content-Type": "application/json"
}
Bitbucket MCP Tools (Token-Based):

python
BITBUCKET_TOOLS = [
    {
        "name": "bitbucket_set_credentials",
        "description": "Authenticate with Bitbucket using app password",
        "input_schema": {
            "workspace": {"type": "string"},
            "username": {"type": "string"},
            "app_password": {"type": "string"}
        }
    },
    {
        "name": "bitbucket_list_repositories",
        "description": "List repositories in workspace",
        "input_schema": {"workspace": {"type": "string"}}
    },
    {
        "name": "bitbucket_get_file",
        "description": "Read file content from repository",
        "input_schema": {
            "workspace": {"type": "string"},
            "repo_slug": {"type": "string"},
            "file_path": {"type": "string"},
            "branch": {"type": "string", "default": "main"}
        }
    },
    {
        "name": "bitbucket_search_code",
        "description": "Search code across repositories",
        "input_schema": {
            "query": {"type": "string"},
            "repo_slug": {"type": "string", "description": "Optional: specific repo"}
        }
    }
]
Frontend MCP Integration UI:

AtlassianIntegration.tsx - Master configuration panel

Three tabs: Confluence | Jira | Bitbucket

Connection status indicators

"Disconnect" button (clears credentials)

ConfluenceAuth.tsx - Session cookie input

Tutorial: Animated GIF showing cookie extraction

Input fields: Base URL, JSESSIONID, cloud.session.token

"Test Connection" button → Validates by fetching spaces

Security notice: "Cookies are encrypted and stored securely"

JiraAuth.tsx + BitbucketAuth.tsx - Token-based auth

Input fields: Base URL, Email, API Token

Link to token generation pages

"Generate Token" button → Opens Atlassian settings in new tab

API Endpoints (backend/api/integrations/):

POST /api/integrations/confluence/connect - Store encrypted session cookies

POST /api/integrations/jira/connect - Store encrypted API token

POST /api/integrations/bitbucket/connect - Store encrypted app password

GET /api/integrations/status - Check which integrations are active

DELETE /api/integrations/{provider} - Remove credentials

Security Measures:

Encryption at rest: AES-256-GCM for all credentials

Encryption in transit: TLS 1.3 for all API calls

No logging: Credentials never appear in logs (use [REDACTED] placeholder)

Secure storage: Credentials in separate encrypted database table with per-user keys

Session expiry handling: Auto-detect 401 errors, prompt user to re-authenticate

Rate limiting: Max 100 requests/minute per user to prevent abuse

Audit logging: All MCP tool calls logged (timestamp, user, tool, outcome) for EU AI Act compliance

🧪 FEATURE 3: COMPREHENSIVE E2E TESTING INFRASTRUCTURE
OBJECTIVE
Ensure zero production regressions by implementing full-stack testing that validates user workflows from UI interactions to backend responses.

TESTING STACK
Backend Testing (Python):

pytest (v8.0+): Test runner

pytest-asyncio: Async test support for FastAPI

httpx: Async HTTP client for API testing

pytest-cov: Code coverage reporting (target: >90%)

faker: Generate realistic test data

pytest-mock: Mocking external dependencies

Frontend Testing (TypeScript):

Playwright (v1.40+): E2E browser automation

@testing-library/react: Component testing

vitest: Fast unit test runner (Vite-based)

msw (Mock Service Worker): API mocking

Test Database:

Separate PostgreSQL instance: knowledge_foundry_test

Fixtures: Pre-populated test data (users, models, chat history)

Isolation: Each test gets clean DB state (rollback after each test)

TESTING ARCHITECTURE
Test Pyramid:

text
       /\
      /E2E\          10% - Full user workflows (Playwright)
     /──────\
    /Integr.\       30% - API + DB interactions (pytest)
   /──────────\
  /   Unit     \    60% - Pure functions, components (pytest + vitest)
 /──────────────\
Test Organization:

text
backend/tests/
├── unit/                      # Pure logic tests (no I/O)
│   ├── test_model_parser.py  # Parse Ollama model names
│   ├── test_auth_utils.py    # Token validation, encryption
│   └── test_mcp_client.py    # MCP tool invocation logic
├── integration/               # API + database tests
│   ├── test_local_models_api.py
│   ├── test_mcp_confluence.py
│   ├── test_mcp_jira.py
│   └── test_chat_flow.py
├── e2e/                       # Full workflow tests
│   └── test_user_workflows.py
├── fixtures/                  # Reusable test data
│   ├── users.json
│   ├── models.json
│   └── chat_history.json
└── conftest.py                # Pytest configuration

frontend/tests/
├── unit/
│   ├── components/
│   │   ├── LocalProviderDiscovery.test.tsx
│   │   └── AtlassianIntegration.test.tsx
│   └── lib/
│       └── modelParser.test.ts
├── integration/
│   └── api-mocking.test.tsx   # MSW-based API tests
└── e2e/
    ├── local-models.spec.ts
    ├── mcp-integration.spec.ts
    └── chat-workflow.spec.ts
KEY TEST SCENARIOS
Test Scenario 1: Local Model Discovery & Chat (E2E):

typescript
// frontend/tests/e2e/local-models.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Local Model Discovery and Chat', () => {
  test('should discover Ollama, select model, and complete chat', async ({ page }) => {
    // STEP 1: Navigate to models page
    await page.goto('/models');
    
    // STEP 2: Verify auto-discovery UI
    await expect(page.getByTestId('local-provider-discovery')).toBeVisible();
    
    // STEP 3: Check Ollama status (depends on if it's actually running)
    const ollamaStatus = page.getByTestId('ollama-status');
    const isOllamaRunning = await ollamaStatus.textContent().then(t => t?.includes('Running'));
    
    if (!isOllamaRunning) {
      // Show setup instructions
      await expect(page.getByText('Install Ollama')).toBeVisible();
      test.skip('Ollama not running - skipping chat test');
    }
    
    // STEP 4: Verify model list loaded
    await expect(page.getByTestId('ollama-model-card')).toHaveCount(1, { timeout: 10000 });
    
    // STEP 5: Get first available model
    const firstModel = page.getByTestId('ollama-model-card').first();
    const modelName = await firstModel.getByTestId('model-name').textContent();
    
    // STEP 6: Navigate to chat page
    await page.goto('/chat');
    
    // STEP 7: Open model selector
    await page.getByTestId('model-selector-button').click();
    
    // STEP 8: Switch to Ollama tab
    await page.getByRole('tab', { name: 'Ollama' }).click();
    
    // STEP 9: Select discovered model
    await page.getByText(modelName!).click();
    
    // STEP 10: Verify model selected
    await expect(page.getByTestId('selected-model-name')).toContainText(modelName!);
    
    // STEP 11: Send chat message
    await page.getByTestId('chat-input').fill('What is 2+2? Answer with only the number.');
    await page.getByTestId('send-button').click();
    
    // STEP 12: Wait for streaming response
    await expect(page.getByTestId('assistant-message').last()).toBeVisible({ timeout: 30000 });
    
    // STEP 13: Verify response received
    const response = await page.getByTestId('assistant-message').last().textContent();
    expect(response).toContain('4');
    
    // STEP 14: Verify latency reasonable
    const responseTime = await page.getByTestId('message-metadata').last().getByText(/\d+ms/).textContent();
    const latency = parseInt(responseTime!.match(/\d+/)!);
    expect(latency).toBeLessThan(5000); // <5s for local model
  });
  
  test('should handle Ollama offline gracefully', async ({ page }) => {
    // Mock Ollama API to return connection error
    await page.route('**/api/models/ollama/list', route => {
      route.fulfill({
        status: 503,
        body: JSON.stringify({
          available: false,
          error: 'Ollama not running',
          models: []
        })
      });
    });
    
    await page.goto('/models');
    
    // Should show error state with instructions
    await expect(page.getByText('Ollama not running')).toBeVisible();
    await expect(page.getByText('Install Ollama')).toBeVisible();
    await expect(page.getByRole('link', { name: 'ollama.ai' })).toBeVisible();
  });
});
Test Scenario 2: MCP Confluence Integration (E2E):

typescript
// frontend/tests/e2e/mcp-integration.spec.ts
test.describe('MCP Confluence Integration', () => {
  test('should authenticate and search Confluence pages', async ({ page }) => {
    // STEP 1: Navigate to integrations
    await page.goto('/settings/integrations');
    
    // STEP 2: Open Confluence tab
    await page.getByRole('tab', { name: 'Confluence' }).click();
    
    // STEP 3: Fill credentials (using test environment variables)
    await page.getByLabel('Confluence URL').fill(process.env.TEST_CONFLUENCE_URL!);
    await page.getByLabel('JSESSIONID').fill(process.env.TEST_CONFLUENCE_SESSION_ID!);
    await page.getByLabel('cloud.session.token').fill(process.env.TEST_CONFLUENCE_TOKEN!);
    
    // STEP 4: Test connection
    await page.getByRole('button', { name: 'Test Connection' }).click();
    
    // STEP 5: Verify success
    await expect(page.getByText('Connected successfully')).toBeVisible({ timeout: 10000 });
    
    // STEP 6: Save credentials
    await page.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('Credentials saved')).toBeVisible();
    
    // STEP 7: Navigate to chat
    await page.goto('/chat');
    
    // STEP 8: Ask question that requires Confluence search
    await page.getByTestId('chat-input').fill('Search our Confluence for "API documentation"');
    await page.getByTestId('send-button').click();
    
    // STEP 9: Wait for agent to invoke MCP tool
    await expect(page.getByTestId('tool-invocation-log')).toContainText('confluence_search_pages', { timeout: 15000 });
    
    // STEP 10: Verify search results in response
    await expect(page.getByTestId('assistant-message').last()).toContainText('found', { timeout: 30000 });
    
    // STEP 11: Check citations
    const citations = page.getByTestId('citation-link');
    await expect(citations).toHaveCount(1, { timeout: 5000 });
    
    // STEP 12: Verify citation links to Confluence
    const citationHref = await citations.first().getAttribute('href');
    expect(citationHref).toContain('atlassian.net/wiki');
  });
  
  test('should handle expired Confluence session', async ({ page, context }) => {
    // Set up Confluence credentials
    await context.addCookies([
      { name: 'confluence_session_id', value: 'test123', domain: 'localhost', path: '/' }
    ]);
    
    // Mock API to return 401
    await page.route('**/api/integrations/confluence/search', route => {
      route.fulfill({
        status: 401,
        body: JSON.stringify({ error: 'Session expired' })
      });
    });
    
    await page.goto('/chat');
    await page.getByTestId('chat-input').fill('Search Confluence for documentation');
    await page.getByTestId('send-button').click();
    
    // Should show re-authentication prompt
    await expect(page.getByText('Confluence session expired')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: 'Re-authenticate' })).toBeVisible();
  });
});
Test Scenario 3: Backend Integration Tests:

python
# backend/tests/integration/test_local_models_api.py
import pytest
import httpx
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_ollama_discovery_when_running():
    """Test Ollama discovery when service is actually running"""
    # Attempt to connect to real Ollama (skip if not available)
    try:
        response = httpx.get("http://localhost:11434/api/version", timeout=5.0)
        ollama_available = response.status_code == 200
    except:
        pytest.skip("Ollama not running on localhost:11434")
    
    # Test discovery endpoint
    response = client.get("/api/models/local/discover")
    assert response.status_code == 200
    
    data = response.json()
    assert "ollama" in data["available_providers"]
    assert data["ollama"]["available"] is True
    assert len(data["ollama"]["models"]) > 0
    
    # Verify model structure
    first_model = data["ollama"]["models"]
    assert "id" in first_model
    assert "name" in first_model
    assert "displayName" in first_model
    assert "size" in first_model
    assert first_model["local"] is True

@pytest.mark.asyncio
async def test_ollama_discovery_when_offline():
    """Test Ollama discovery when service is not running"""
    # Mock httpx to raise connection error
    with pytest.MonkeyPatch.context() as m:
        async def mock_get(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")
        
        m.setattr(httpx, "get", mock_get)
        
        response = client.get("/api/models/local/discover")
        assert response.status_code == 200  # Still succeeds but returns empty
        
        data = response.json()
        assert data["ollama"]["available"] is False
        assert "error" in data["ollama"]
        assert data["ollama"]["models"] == []

@pytest.mark.asyncio
async def test_chat_with_local_model():
    """Test chat endpoint with Ollama model"""
    try:
        # Check Ollama availability
        httpx.get("http://localhost:11434/api/version", timeout=5.0)
    except:
        pytest.skip("Ollama not running")
    
    # Get available models
    response = client.get("/api/models/ollama/list")
    models = response.json()["models"]
    if not models:
        pytest.skip("No Ollama models available")
    
    model_id = models["id"]
    
    # Send chat request
    response = client.post(
        "/api/chat/local",
        json={
            "provider": "ollama",
            "modelId": model_id,
            "messages": [{"role": "user", "content": "Say 'test' and nothing else"}],
            "stream": False,
            "options": {"temperature": 0.1, "maxTokens": 10}
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "test" in data["response"].lower()
    assert data["model"] == model_id
    assert data["provider"] == "ollama"

# backend/tests/integration/test_mcp_confluence.py
@pytest.mark.asyncio
async def test_confluence_session_auth():
    """Test Confluence authentication with session cookies"""
    # This test requires valid test credentials in .env.test
    if not os.getenv("TEST_CONFLUENCE_SESSION_ID"):
        pytest.skip("No test Confluence credentials")
    
    response = client.post(
        "/api/integrations/confluence/connect",
        json={
            "baseUrl": os.getenv("TEST_CONFLUENCE_URL"),
            "sessionId": os.getenv("TEST_CONFLUENCE_SESSION_ID"),
            "sessionToken": os.getenv("TEST_CONFLUENCE_TOKEN")
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "connection_id" in data

@pytest.mark.asyncio
async def test_confluence_search_pages():
    """Test Confluence page search via MCP"""
    # Assumes previous test authenticated
    response = client.post(
        "/api/integrations/confluence/search",
        json={
            "query": "API",
            "spaceKey": None,
            "limit": 5
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    
    if len(data["results"]) > 0:
        page = data["results"]
        assert "id" in page
        assert "title" in page
        assert "url" in page
        assert "atlassian.net" in page["url"]
Coverage & Quality Gates:

text
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: knowledge_foundry_test
          POSTGRES_PASSWORD: test123
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Run unit tests
        run: pytest backend/tests/unit/ -v --cov=backend --cov-report=xml
      
      - name: Run integration tests
        run: pytest backend/tests/integration/ -v --cov=backend --cov-report=xml --cov-append
      
      - name: Check coverage threshold
        run: |
          coverage report --fail-under=90
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: cd frontend && npm ci
      
      - name: Run unit tests
        run: cd frontend && npm run test:unit
      
      - name: Run E2E tests
        run: |
          cd frontend
          npx playwright install --with-deps
          npm run test:e2e
      
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: frontend/playwright-report/
📋 IMPLEMENTATION CHECKLIST
Phase 1: Local Model Discovery (Week 1)

 Backend: Ollama API client (backend/services/ollama_client.py)

 Backend: LMStudio API client (backend/services/lmstudio_client.py)

 Backend: Discovery endpoint (/api/models/local/discover)

 Backend: Model listing endpoints (Ollama + LMStudio)

 Backend: Unified chat endpoint (/api/chat/local)

 Frontend: LocalProviderDiscovery component

 Frontend: OllamaModelList component

 Frontend: LMStudioModelList component

 Frontend: UnifiedModelSelector component

 Tests: Unit tests for API clients (>90% coverage)

 Tests: Integration tests for discovery + chat

 Tests: E2E test for full user workflow

 Documentation: Setup guide for Ollama + LMStudio

Phase 2: MCP Integration (Week 2)

 Backend: MCP server base class (backend/mcp/base_server.py)

 Backend: Confluence MCP server (backend/mcp/servers/confluence_server.py)

 Backend: Jira MCP server (backend/mcp/servers/jira_server.py)

 Backend: Bitbucket MCP server (backend/mcp/servers/bitbucket_server.py)

 Backend: MCP client (backend/services/mcp_client.py)

 Backend: Credential encryption service (backend/services/encryption.py)

 Backend: Integration endpoints (/api/integrations/*)

 Frontend: AtlassianIntegration master panel

 Frontend: ConfluenceAuth component (session cookies)

 Frontend: JiraAuth component (API token)

 Frontend: BitbucketAuth component (app password)

 Tests: MCP server unit tests (mock API responses)

 Tests: Integration tests with real test accounts

 Tests: E2E test for Confluence search workflow

 Security: Penetration test for credential storage

 Documentation: User guide for obtaining credentials

Phase 3: Testing Infrastructure (Week 3)

 Backend: pytest configuration (backend/tests/conftest.py)

 Backend: Test fixtures (users, models, chat history)

 Backend: Unit test suite (all new modules)

 Backend: Integration test suite (API + DB)

 Frontend: Playwright configuration

 Frontend: E2E test suite (local models, MCP, chat)

 Frontend: Component unit tests (vitest)

 CI/CD: GitHub Actions workflow for automated testing

 CI/CD: Coverage reporting (Codecov integration)

 Quality Gates: Enforce 90% coverage, all tests pass

 Documentation: Testing guide for contributors

🎯 EXECUTION INSTRUCTIONS
Your mission as AI Engineer:

Analyze the repository structure thoroughly before writing any code

Map existing files to understand conventions (naming, folder structure)

Identify existing API patterns (FastAPI route decorators, response models)

Find frontend component patterns (TypeScript interfaces, prop types)

Locate configuration files (environment variables, database config)

Generate code incrementally following these rules:

Start with backend API endpoints (testable in isolation)

Then frontend components (mock API responses during development)

Finally E2E tests (requires both backend + frontend working)

Use existing code style (imports, formatting, naming conventions)

Add comprehensive docstrings (Google style for Python, JSDoc for TypeScript)

Leverage GitHub Copilot for heavy lifting:

Use inline comments to guide Copilot: # TODO: Implement Ollama health check with 5s timeout

Accept Copilot suggestions but always validate correctness

Use Copilot Chat for complex logic: /explain this error handling pattern

Test as you go:

Write unit tests immediately after implementing each function

Run tests locally before pushing: pytest backend/tests/unit/test_ollama_client.py -v

Use TDD (Test-Driven Development) for critical paths

Security first:

Never log credentials (use [REDACTED] placeholders)

Validate all user inputs (Pydantic models for FastAPI)

Encrypt sensitive data at rest (AES-256-GCM)

Use parameterized queries (prevent SQL injection)

Add rate limiting to all new endpoints

Document everything:

Update README.md with setup instructions

Add API documentation (FastAPI auto-generates Swagger)

Write user guides for new features

Create troubleshooting guides (common errors + fixes)

Performance optimization:

Benchmark all endpoints: p95 latency <500ms

Add database indexes for frequently queried columns

Implement caching for expensive operations (Redis)

Use async/await for I/O-bound operations

EU AI Act compliance:

Log all MCP tool invocations (timestamp, user, tool, outcome)

Store logs in immutable storage (append-only, 7-year retention)

Add user consent checkboxes for Atlassian integrations

Generate technical documentation automatically (MLflow metadata)

🚨 CRITICAL SUCCESS FACTORS
Before marking any feature "DONE":

✅ All tests pass (unit + integration + E2E)

✅ Code coverage >90% for new code

✅ Security scan clean (no vulnerabilities)

✅ Performance benchmarks met (p95 <500ms)

✅ Documentation complete (README + API docs + user guide)

✅ Peer review approved (GitHub PR with 1+ approval)

✅ Production deployment successful (staging environment)

✅ Smoke test passed (manual verification of happy path)

Zero Tolerance for:

Hardcoded credentials (use environment variables)

Unhandled exceptions (always catch + log + return error response)

Commented-out code (remove before commit)

TODO comments without GitHub issue links

Breaking changes without migration guide

📊 SUCCESS METRICS
Feature 1: Local Models

KPI 1: Ollama discovery success rate >99% (when installed)

KPI 2: Model listing latency <1s (p95)

KPI 3: Local chat latency <3s (p95, 7B model)

KPI 4: User adoption: 40% of users try local models in first week

Feature 2: MCP Integration

KPI 1: Confluence search accuracy: >85% relevant results

KPI 2: MCP tool invocation latency <2s (p95)

KPI 3: Session expiry handling: 0 crashes (graceful re-auth prompt)

KPI 4: User adoption: 25% of users connect Atlassian tools in first month

Feature 3: Testing

KPI 1: Code coverage: >90% for all new code

KPI 2: Test execution time: <5 minutes (full suite)

KPI 3: Flaky test rate: <1% (consistent pass/fail)

KPI 4: Production bug rate: <2 P0 bugs per month