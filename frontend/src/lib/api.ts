/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — API Client
   Centralized API calls to backend
   ═══════════════════════════════════════════════════════════ */

import type {
    LocalDiscoveryResponse,
    ProviderStatus,
    LocalChatRequest,
    LocalChatResponse,
    RAGResponse,
    ExportFormatInfo,
    ExportRequest,
    ExportEntityType,
    ListFormatsResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    async connectConfluence(baseUrl: string, sessionId: string, sessionToken: string): Promise<unknown> {
        return this.request("/api/integrations/confluence/connect", {
            method: "POST",
            body: JSON.stringify({
                base_url: baseUrl,
                session_id: sessionId,
                session_token: sessionToken,
            }),
        });
    }

    async connectJira(baseUrl: string, email: string, apiToken: string): Promise<unknown> {
        return this.request("/api/integrations/jira/connect", {
            method: "POST",
            body: JSON.stringify({
                base_url: baseUrl,
                email: email,
                api_token: apiToken,
            }),
        });
    }

    async connectBitbucket(workspace: string, username: string, appPassword: string): Promise<unknown> {
        return this.request("/api/integrations/bitbucket/connect", {
            method: "POST",
            body: JSON.stringify({
                workspace: workspace,
                username: username,
                app_password: appPassword,
            }),
        });
    }

    async getIntegrationStatus(): Promise<unknown> {
        return this.request("/api/integrations/status");
    }

    async disconnectIntegration(provider: string): Promise<unknown> {
        return this.request(`/api/integrations/${provider}`, {
            method: "DELETE",
        });
    }

    // Export API
    async listExportFormats(entityType?: ExportEntityType): Promise<ListFormatsResponse> {
        const params = entityType ? `?entity_type=${entityType}` : "";
        return this.request<ListFormatsResponse>(`/v1/export/formats${params}`);
    }

    async getExportFormatInfo(formatId: string): Promise<ExportFormatInfo> {
        return this.request<ExportFormatInfo>(`/v1/export/formats/${formatId}`);
    }

    async generateExport(request: ExportRequest): Promise<Blob> {
        const url = `${this.baseURL}/v1/export/generate`;
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return response.blob();
    }

    async generateExportWithFilename(request: ExportRequest): Promise<{ blob: Blob; filename: string }> {
        const url = `${this.baseURL}/v1/export/generate`;
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        const contentDisposition = response.headers.get("Content-Disposition");
        let filename = "export";
        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?([^"]+)"?/);
            if (match) {
                filename = match[1];
            }
        }

        const blob = await response.blob();
        return { blob, filename };
    }
}

export const apiClient = new APIClient();
export default apiClient;

// Stream Query function for RAG pipeline
export async function streamQuery(
    query: string,
    onChunk: (text: string) => void,
    onComplete: (response: RAGResponse) => void,
    onError: (error: Error) => void,
    options?: { model?: string; signal?: AbortSignal }
): Promise<void> {
    const tenantId = "00000000-0000-0000-0000-000000000001"; // Default tenant for demo

    try {
        const response = await fetch(`${API_BASE_URL}/v1/query`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                query,
                tenant_id: tenantId,
                model_tier: options?.model || "sonnet",
            }),
            signal: options?.signal,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();

        // Convert API response to RAGResponse format
        const ragResponse: RAGResponse = {
            text: data.answer,
            citations: data.citations || [],
            routing_decision: data.routing,
            llm_response: data.performance ? {
                text: data.answer,
                model: data.routing?.final_tier || "sonnet",
                tier: data.routing?.final_tier || "sonnet",
                confidence: data.confidence,
                input_tokens: data.performance.input_tokens,
                output_tokens: data.performance.output_tokens,
                latency_ms: data.performance.llm_latency_ms,
                cost_usd: data.performance.cost_usd,
            } : undefined,
            search_results: [],
            total_latency_ms: data.performance?.total_latency_ms || 0,
        };

        // Simulate streaming by delivering chunks
        const words = data.answer.split(" ");
        let currentText = "";
        for (let i = 0; i < words.length; i++) {
            currentText += (i > 0 ? " " : "") + words[i];
            onChunk(currentText);
            // Small delay to simulate streaming
            await new Promise((resolve) => setTimeout(resolve, 10));
        }

        onComplete(ragResponse);
    } catch (error) {
        if (error instanceof Error) {
            if (error.name === "AbortError") {
                return; // User cancelled
            }
            onError(error);
        } else {
            onError(new Error("Unknown error occurred"));
        }
    }
}
