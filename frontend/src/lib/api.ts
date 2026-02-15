/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — API Client
   Centralized API calls to backend
   ═══════════════════════════════════════════════════════════ */

import type {
    LocalDiscoveryResponse,
    ProviderStatus,
    LocalChatRequest,
    LocalChatResponse,
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
}

export const apiClient = new APIClient();
export default apiClient;
