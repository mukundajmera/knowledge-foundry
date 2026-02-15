/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Type Definitions
   Shared TypeScript interfaces and types
   ═══════════════════════════════════════════════════════════ */

// Query Options
export interface QueryOptions {
    model: "auto" | "opus" | "sonnet" | "haiku" | string;
    deepSearch?: boolean;
    multiHop?: boolean;
    files?: FileAttachment[];
}

// File Attachment
export interface FileAttachment {
    id?: string;
    name: string;
    size: number;
    type: string;
    file?: File;
    preview?: string;
}

// Citation from RAG retrieval
export interface Citation {
    title: string;
    section?: string;
    relevance_score: number;
    document_id?: string;
    chunk_id?: string;
}

// Routing decision from the tiered intelligence router
export interface RoutingDecision {
    initial_tier: string;
    final_tier: string;
    escalated: boolean;
    escalation_reason?: string;
    complexity_score: number;
    task_type_detected?: string;
}

// Chat message in a conversation
export interface Message {
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    timestamp: number;
    isStreaming?: boolean;
    model?: string;
    citations?: Citation[];
    confidence?: number;
    latency_ms?: number;
    cost_usd?: number;
    routing?: RoutingDecision;
    followUps?: string[];
    error?: {
        type: "rate_limit" | "no_results" | "system_error" | "low_confidence";
        retryAfterSeconds?: number;
        message?: string;
    };
}

// RAG response from the backend
export interface RAGResponse {
    text: string;
    citations?: Citation[];
    total_latency_ms?: number;
    llm_response?: {
        tier?: string;
        confidence?: number;
        cost_usd?: number;
    };
}

// Conversation with messages
export interface Conversation {
    id: string;
    title: string;
    messages: Message[];
    createdAt: number;
    updatedAt: number;
}

// Local Model Types
export interface LocalModel {
    id: string;
    name: string;
    displayName: string;
    family?: string;
    parameters?: string;
    quantization?: string;
    size?: number;
    digest?: string;
    modified?: string;
    local: boolean;
}

export interface LocalProvider {
    name: string;
    available: boolean;
    port: number;
    models: LocalModel[];
}

export interface ProviderStatus {
    provider: string;
    available: boolean;
    error?: string;
    models: LocalModel[];
    count: number;
}

export interface LocalDiscoveryResponse {
    available_providers: string[];
    ollama: ProviderStatus;
    lmstudio: ProviderStatus;
}

export interface ChatMessage {
    role: "user" | "assistant" | "system";
    content: string;
}

export interface LocalChatRequest {
    provider: "ollama" | "lmstudio";
    modelId: string;
    messages: ChatMessage[];
    stream?: boolean;
    options?: {
        temperature?: number;
        maxTokens?: number;
    };
}

export interface LocalChatResponse {
    success: boolean;
    response: string;
    model: string;
    provider: string;
    tokens: {
        input: number;
        output: number;
    };
    latency_ms: number;
    cost_usd: number;
}

// MCP Types
export interface AtlassianCredentials {
    provider: "confluence" | "jira" | "bitbucket";
    baseUrl: string;
    sessionId?: string;
    sessionToken?: string;
    email?: string;
    apiToken?: string;
    appPassword?: string;
}

export interface MCPIntegrationStatus {
    confluence: boolean;
    jira: boolean;
    bitbucket: boolean;
}

export interface ConfluenceConnectRequest {
    base_url: string;
    session_id: string;
    session_token: string;
}

export interface JiraConnectRequest {
    base_url: string;
    email: string;
    api_token: string;
}

export interface BitbucketConnectRequest {
    workspace: string;
    username: string;
    app_password: string;
}

export interface IntegrationResponse {
    success: boolean;
    message: string;
    connection_id?: string;
}
