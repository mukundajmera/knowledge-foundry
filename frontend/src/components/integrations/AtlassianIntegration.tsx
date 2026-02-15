/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Atlassian Integration Panel
   Master panel for connecting to Confluence, Jira, and Bitbucket
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";
import ConfluenceAuth from "./ConfluenceAuth";
import JiraAuth from "./JiraAuth";
import BitbucketAuth from "./BitbucketAuth";

export default function AtlassianIntegration() {
    const [activeTab, setActiveTab] = useState<"confluence" | "jira" | "bitbucket">("confluence");
    const [status, setStatus] = useState({
        confluence: false,
        jira: false,
        bitbucket: false,
    });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadStatus();
    }, []);

    const loadStatus = async () => {
        try {
            setLoading(true);
            const result = await apiClient.getIntegrationStatus();
            setStatus(result);
        } catch (err) {
            console.error("Failed to load integration status:", err);
        } finally {
            setLoading(false);
        }
    };

    const handleConnectConfluence = async (
        baseUrl: string,
        sessionId: string,
        sessionToken: string
    ) => {
        await apiClient.connectConfluence(baseUrl, sessionId, sessionToken);
        await loadStatus();
    };

    const handleConnectJira = async (
        baseUrl: string,
        email: string,
        apiToken: string
    ) => {
        await apiClient.connectJira(baseUrl, email, apiToken);
        await loadStatus();
    };

    const handleConnectBitbucket = async (
        workspace: string,
        username: string,
        appPassword: string
    ) => {
        await apiClient.connectBitbucket(workspace, username, appPassword);
        await loadStatus();
    };

    const handleDisconnect = async (provider: string) => {
        if (confirm(`Disconnect from ${provider}?`)) {
            try {
                await apiClient.disconnectIntegration(provider);
                await loadStatus();
            } catch (err) {
                console.error(`Failed to disconnect from ${provider}:`, err);
            }
        }
    };

    if (loading) {
        return (
            <div className="p-6">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
                    <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold">Atlassian Integrations</h2>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                    {Object.values(status).filter(Boolean).length} / 3 connected
                </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-300 dark:border-gray-700">
                <button
                    onClick={() => setActiveTab("confluence")}
                    className={`px-4 py-2 border-b-2 transition-colors ${
                        activeTab === "confluence"
                            ? "border-blue-600 text-blue-600 font-medium"
                            : "border-transparent hover:border-gray-400"
                    }`}
                >
                    Confluence {status.confluence && "✓"}
                </button>
                <button
                    onClick={() => setActiveTab("jira")}
                    className={`px-4 py-2 border-b-2 transition-colors ${
                        activeTab === "jira"
                            ? "border-blue-600 text-blue-600 font-medium"
                            : "border-transparent hover:border-gray-400"
                    }`}
                >
                    Jira {status.jira && "✓"}
                </button>
                <button
                    onClick={() => setActiveTab("bitbucket")}
                    className={`px-4 py-2 border-b-2 transition-colors ${
                        activeTab === "bitbucket"
                            ? "border-blue-600 text-blue-600 font-medium"
                            : "border-transparent hover:border-gray-400"
                    }`}
                >
                    Bitbucket {status.bitbucket && "✓"}
                </button>
            </div>

            {/* Tab Content */}
            <div className="border rounded-lg p-6 bg-white dark:bg-gray-800">
                {activeTab === "confluence" && (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold">Confluence Connection</h3>
                            {status.confluence && (
                                <button
                                    onClick={() => handleDisconnect("confluence")}
                                    className="text-sm text-red-600 hover:text-red-700"
                                >
                                    Disconnect
                                </button>
                            )}
                        </div>
                        <ConfluenceAuth
                            onConnect={handleConnectConfluence}
                            isConnected={status.confluence}
                        />
                    </div>
                )}

                {activeTab === "jira" && (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold">Jira Connection</h3>
                            {status.jira && (
                                <button
                                    onClick={() => handleDisconnect("jira")}
                                    className="text-sm text-red-600 hover:text-red-700"
                                >
                                    Disconnect
                                </button>
                            )}
                        </div>
                        <JiraAuth
                            onConnect={handleConnectJira}
                            isConnected={status.jira}
                        />
                    </div>
                )}

                {activeTab === "bitbucket" && (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold">Bitbucket Connection</h3>
                            {status.bitbucket && (
                                <button
                                    onClick={() => handleDisconnect("bitbucket")}
                                    className="text-sm text-red-600 hover:text-red-700"
                                >
                                    Disconnect
                                </button>
                            )}
                        </div>
                        <BitbucketAuth
                            onConnect={handleConnectBitbucket}
                            isConnected={status.bitbucket}
                        />
                    </div>
                )}
            </div>

            {/* Information */}
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-300 dark:border-blue-700 rounded p-4">
                <h4 className="font-medium text-blue-900 dark:text-blue-300 mb-2">
                    About Atlassian Integrations
                </h4>
                <p className="text-sm text-blue-800 dark:text-blue-400">
                    Connect Knowledge Foundry to your Atlassian tools to search documentation,
                    query issues, and access code repositories directly from your AI conversations.
                    All credentials are stored securely and encrypted.
                </p>
            </div>
        </div>
    );
}
