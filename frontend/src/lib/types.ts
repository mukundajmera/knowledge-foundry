/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Type Definitions
   Shared TypeScript interfaces and types
   ═══════════════════════════════════════════════════════════ */

// Query Options
export interface QueryOptions {
    model: "auto" | "opus" | "sonnet" | "haiku" | string;
    deepSearch?: boolean;
    multiHop?: boolean;
}

// File Attachment
export interface FileAttachment {
    id: string;
    name: string;
    size: number;
    type: string;
    preview?: string;
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
