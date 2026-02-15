/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — API Client
   Centralized API calls to backend
   ═══════════════════════════════════════════════════════════ */

import type {
    LocalDiscoveryResponse,
    ProviderStatus,
    LocalChatRequest,
    LocalChatResponse,
    IntegrationResponse,
    MCPIntegrationStatus,
    RAGResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Stream a query to the RAG backend via POST /api/query.
 *
 * Sends the query and reads the response as a stream of JSON chunks,
 * invoking callbacks for progressive text updates, completion, and errors.
 */
export async function streamQuery(
    query: string,
    onChunk: (text: string) => void,
    onComplete: (response: RAGResponse) => void,
    onError: (err: Error) => void,
    options?: { model?: string; signal?: AbortSignal },
): Promise<void> {
    try {
        const response = await fetch(`${API_BASE_URL}/api/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query,
                model: options?.model ?? "auto",
                stream: true,
            }),
            signal: options?.signal,
        });

        if (!response.ok) {
            const errBody = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errBody.detail || `HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error("ReadableStream not supported");
        }

        const decoder = new TextDecoder();
        let accumulated = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            accumulated += chunk;
            onChunk(accumulated);
        }

        // Build final response object
        const ragResponse: RAGResponse = {
            text: accumulated,
        };
        onComplete(ragResponse);
    } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
            return; // silently ignore aborted requests
        }
        onError(err instanceof Error ? err : new Error(String(err)));
    }
}

class APIClient {
    private baseURL: string;

    constructor(baseURL: string = API_BASE_URL) {
        this.baseURL = baseURL;
    }

    private async request<T>(
        endpoint: string,
        options?: RequestInit
    ): Promise<T> {
        const url = `${this.baseURL}${endpoint}`;
        const response = await fetch(url, {
            headers: {
                "Content-Type": "application/json",
                ...options?.headers,
            },
            ...options,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return response.json();
    }

    // Local Model Discovery
    async discoverLocalProviders(): Promise<LocalDiscoveryResponse> {
        return this.request<LocalDiscoveryResponse>("/api/models/local/discover");
    }

    async listOllamaModels(): Promise<ProviderStatus> {
        return this.request<ProviderStatus>("/api/models/ollama/list");
    }

    async listLMStudioModels(): Promise<ProviderStatus> {
        return this.request<ProviderStatus>("/api/models/lmstudio/list");
    }

    async pullOllamaModel(modelName: string): Promise<{ success: boolean; message: string }> {
        return this.request("/api/models/ollama/pull", {
            method: "POST",
            body: JSON.stringify({ modelName }),
        });
    }

    async deleteOllamaModel(modelName: string): Promise<{ success: boolean; message: string }> {
        return this.request(`/api/models/ollama/${encodeURIComponent(modelName)}`, {
            method: "DELETE",
        });
    }

    async chatWithLocalModel(request: LocalChatRequest): Promise<LocalChatResponse> {
        return this.request<LocalChatResponse>("/api/models/chat/local", {
            method: "POST",
            body: JSON.stringify(request),
        });
    }

    // MCP Integrations
    async connectConfluence(baseUrl: string, sessionId: string, sessionToken: string): Promise<IntegrationResponse> {
        return this.request<IntegrationResponse>("/api/integrations/confluence/connect", {
            method: "POST",
            body: JSON.stringify({
                base_url: baseUrl,
                session_id: sessionId,
                session_token: sessionToken,
            }),
        });
    }

    async connectJira(baseUrl: string, email: string, apiToken: string): Promise<IntegrationResponse> {
        return this.request<IntegrationResponse>("/api/integrations/jira/connect", {
            method: "POST",
            body: JSON.stringify({
                base_url: baseUrl,
                email: email,
                api_token: apiToken,
            }),
        });
    }

    async connectBitbucket(workspace: string, username: string, appPassword: string): Promise<IntegrationResponse> {
        return this.request<IntegrationResponse>("/api/integrations/bitbucket/connect", {
            method: "POST",
            body: JSON.stringify({
                workspace: workspace,
                username: username,
                app_password: appPassword,
            }),
        });
    }

    async getIntegrationStatus(): Promise<MCPIntegrationStatus> {
        return this.request<MCPIntegrationStatus>("/api/integrations/status");
    }

    async disconnectIntegration(provider: string): Promise<IntegrationResponse> {
        return this.request<IntegrationResponse>(`/api/integrations/${provider}`, {
            method: "DELETE",
        });
    }
}

export const apiClient = new APIClient();
export default apiClient;
