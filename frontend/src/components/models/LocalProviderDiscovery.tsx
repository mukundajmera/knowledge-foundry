/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Local Provider Discovery Component
   Auto-discovers running local LLM providers (Ollama, LMStudio)
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/lib/api";
import type { LocalDiscoveryResponse } from "@/lib/types";

export default function LocalProviderDiscovery() {
    const [discovery, setDiscovery] = useState<LocalDiscoveryResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showSetupModal, setShowSetupModal] = useState<string | null>(null);

    const discoverProviders = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const result = await apiClient.discoverLocalProviders();
            setDiscovery(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to discover providers");
        } finally {
            setLoading(false);
        }
    }, []);

    // Auto-refresh every 30 seconds
    useEffect(() => {
        discoverProviders();
        const interval = setInterval(discoverProviders, 30000);
        return () => clearInterval(interval);
    }, [discoverProviders]);

    const getProviderStatus = (provider: "ollama" | "lmstudio") => {
        if (!discovery) return null;
        return discovery[provider];
    };

    const renderProviderCard = (provider: "ollama" | "lmstudio") => {
        const status = getProviderStatus(provider);
        if (!status) return null;

        const providerName = provider === "ollama" ? "Ollama" : "LM Studio";
        const port = provider === "ollama" ? 11434 : 1234;
        const isAvailable = status.available;

        return (
            <div
                key={provider}
                className="border rounded-lg p-4 bg-white dark:bg-gray-800"
            >
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        <span className={`text-2xl ${isAvailable ? "🟢" : "🔴"}`}>
                            {isAvailable ? "🟢" : "🔴"}
                        </span>
                        {providerName}
                    </h3>
                    <span className="text-sm text-gray-500">Port {port}</span>
                </div>

                {isAvailable ? (
                    <div className="space-y-2">
                        <p className="text-sm text-green-600 dark:text-green-400">
                            Running • {status.count} model{status.count !== 1 ? "s" : ""} available
                        </p>
                        <div className="text-xs text-gray-600 dark:text-gray-400">
                            {status.models.slice(0, 3).map((model) => (
                                <div key={model.id} className="truncate">
                                    • {model.displayName}
                                </div>
                            ))}
                            {status.count > 3 && (
                                <div className="text-gray-500">
                                    ...and {status.count - 3} more
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="space-y-2">
                        <p className="text-sm text-red-600 dark:text-red-400">
                            Not Detected
                        </p>
                        {status.error && (
                            <p className="text-xs text-gray-600 dark:text-gray-400">
                                {status.error}
                            </p>
                        )}
                        <button
                            onClick={() => setShowSetupModal(provider)}
                            className="text-xs text-blue-600 hover:text-blue-700 underline"
                        >
                            View setup instructions
                        </button>
                    </div>
                )}
            </div>
        );
    };

    const renderSetupModal = () => {
        if (!showSetupModal) return null;

        const instructions = showSetupModal === "ollama" ? {
            title: "Install Ollama",
            steps: [
                "Visit https://ollama.ai",
                "Download and install Ollama for your OS",
                "Run: ollama serve",
                "Pull a model: ollama pull llama3:8b",
                "Refresh this page to detect"
            ],
            website: "https://ollama.ai"
        } : {
            title: "Install LM Studio",
            steps: [
                "Visit https://lmstudio.ai",
                "Download and install LM Studio",
                "Open LM Studio and load a model",
                "Click 'Start Server' in the Local Server tab",
                "Refresh this page to detect"
            ],
            website: "https://lmstudio.ai"
        };

        return (
            <div
                className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
                onClick={() => setShowSetupModal(null)}
            >
                <div
                    className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4"
                    onClick={(e) => e.stopPropagation()}
                >
                    <h2 className="text-xl font-bold mb-4">{instructions.title}</h2>
                    <ol className="list-decimal list-inside space-y-2 mb-4">
                        {instructions.steps.map((step, idx) => (
                            <li key={idx} className="text-sm text-gray-700 dark:text-gray-300">
                                {step}
                            </li>
                        ))}
                    </ol>
                    <div className="flex gap-2">
                        <a
                            href={instructions.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-1 bg-blue-600 text-white px-4 py-2 rounded text-center hover:bg-blue-700"
                        >
                            Visit Website
                        </a>
                        <button
                            onClick={() => setShowSetupModal(null)}
                            className="flex-1 bg-gray-200 dark:bg-gray-700 px-4 py-2 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
                        >
                            Close
                        </button>
                    </div>
                </div>
            </div>
        );
    };

    if (loading && !discovery) {
        return (
            <div className="border rounded-lg p-6 bg-white dark:bg-gray-800">
                <div className="animate-pulse space-y-4">
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="border border-red-300 rounded-lg p-4 bg-red-50 dark:bg-red-900/20">
                <p className="text-red-700 dark:text-red-300">Error: {error}</p>
                <button
                    onClick={discoverProviders}
                    className="mt-2 text-sm text-red-600 dark:text-red-400 underline"
                >
                    Retry
                </button>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold">Local LLM Providers</h2>
                <button
                    onClick={discoverProviders}
                    disabled={loading}
                    className="text-sm px-3 py-1 rounded border hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                    {loading ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {renderProviderCard("ollama")}
                {renderProviderCard("lmstudio")}
            </div>

            {discovery && discovery.available_providers.length === 0 && (
                <div className="border border-yellow-300 rounded-lg p-4 bg-yellow-50 dark:bg-yellow-900/20">
                    <p className="text-yellow-800 dark:text-yellow-300">
                        No local providers detected. Install Ollama or LM Studio to use local models.
                    </p>
                </div>
            )}

            {renderSetupModal()}
        </div>
    );
}
