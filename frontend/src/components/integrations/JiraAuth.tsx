/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Jira Authentication Component
   Token-based authentication for Jira integration
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";

interface JiraAuthProps {
    onConnect: (baseUrl: string, email: string, apiToken: string) => Promise<void>;
    isConnected: boolean;
}

export default function JiraAuth({ onConnect, isConnected }: JiraAuthProps) {
    const [baseUrl, setBaseUrl] = useState("https://company.atlassian.net");
    const [email, setEmail] = useState("");
    const [apiToken, setApiToken] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            await onConnect(baseUrl, email, apiToken);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to connect");
        } finally {
            setLoading(false);
        }
    };

    if (isConnected) {
        return (
            <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-300 dark:border-green-700 rounded">
                <p className="text-green-700 dark:text-green-300">
                    ✅ Connected to Jira
                </p>
            </div>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div>
                <label className="block text-sm font-medium mb-1">
                    Jira URL
                </label>
                <input
                    type="url"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://company.atlassian.net"
                    required
                    className="w-full px-3 py-2 border rounded dark:bg-gray-800"
                />
            </div>

            <div>
                <label className="block text-sm font-medium mb-1">
                    Email Address
                </label>
                <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="user@company.com"
                    required
                    className="w-full px-3 py-2 border rounded dark:bg-gray-800"
                />
            </div>

            <div>
                <label className="block text-sm font-medium mb-1">
                    API Token
                </label>
                <input
                    type="password"
                    value={apiToken}
                    onChange={(e) => setApiToken(e.target.value)}
                    placeholder="Enter your Jira API token"
                    required
                    className="w-full px-3 py-2 border rounded dark:bg-gray-800"
                />
            </div>

            {error && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-300 dark:border-red-700 rounded">
                    <p className="text-red-700 dark:text-red-300 text-sm">{error}</p>
                </div>
            )}

            <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
                {loading ? "Connecting..." : "Connect to Jira"}
            </button>

            <div className="text-xs text-gray-600 dark:text-gray-400">
                <p className="font-medium mb-1">How to create an API token:</p>
                <ol className="list-decimal list-inside space-y-1">
                    <li>Go to https://id.atlassian.com/manage-profile/security/api-tokens</li>
                    <li>Click &quot;Create API token&quot;</li>
                    <li>Give it a label and copy the token</li>
                </ol>
            </div>
        </form>
    );
}
