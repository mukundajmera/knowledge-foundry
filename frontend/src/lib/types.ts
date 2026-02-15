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
    file?: File;
}

// Citation
export interface Citation {
    document_id: string;
    title: string;
    chunk_id?: string;
    section?: string;
    relevance_score: number;
}

// Routing Decision
export interface RoutingDecision {
    initial_tier: string;
    final_tier: string;
    escalated: boolean;
    escalation_reason?: string;
    complexity_score: number;
    task_type_detected?: string;
}

// Message Error
export interface MessageError {
    type: "rate_limit" | "no_results" | "system_error" | "low_confidence";
    message?: string;
    retryAfterSeconds?: number;
}

// Message
export interface Message {
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    timestamp: number;
    citations?: Citation[];
    model?: string;
    confidence?: number;
    latency_ms?: number;
    cost_usd?: number;
    isStreaming?: boolean;
    followUps?: string[];
    error?: MessageError;
    routing?: RoutingDecision;
}

// Conversation
export interface Conversation {
    id: string;
    title: string;
    messages: Message[];
    createdAt: number;
    updatedAt: number;
}

// RAG Response
export interface LLMResponse {
    text: string;
    model: string;
    tier: string;
    confidence?: number;
    input_tokens: number;
    output_tokens: number;
    latency_ms: number;
    cost_usd: number;
}

export interface RAGResponse {
    text: string;
    citations: Citation[];
    routing_decision?: RoutingDecision;
    llm_response?: LLMResponse;
    search_results: { chunk_id: string; document_id: string; text: string; score: number }[];
    total_latency_ms: number;
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

// Export Types
export type ExportEntityType = "conversation" | "message" | "rag_run" | "evaluation_report";
export type ExportFormatId = "markdown" | "html" | "pdf" | "docx" | "json" | "text";

export interface ExportFormatInfo {
    format_id: ExportFormatId;
    label: string;
    description: string;
    mime_type: string;
    extension: string;
    supported_entity_types: ExportEntityType[];
    options_schema: Record<string, unknown>;
}

export interface ExportOptions {
    include_metadata: boolean;
    include_citations: boolean;
    anonymize_user: boolean;
    include_raw_json_appendix: boolean;
    locale: string;
}

export interface ExportRequest {
    entity_type: ExportEntityType;
    entity_id: string;
    format_id: ExportFormatId;
    options: Partial<ExportOptions>;
    entity_data?: Record<string, unknown>;
}

export interface ListFormatsResponse {
    formats: ExportFormatInfo[];
    entity_type?: string;
}
