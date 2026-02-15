/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Confluence Authentication Component
   Session-based authentication for Confluence integration
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";

interface ConfluenceAuthProps {
    onConnect: (baseUrl: string, sessionId: string, sessionToken: string) => Promise<void>;
    isConnected: boolean;
}

export default function ConfluenceAuth({ onConnect, isConnected }: ConfluenceAuthProps) {
    const [baseUrl, setBaseUrl] = useState("https://company.atlassian.net/wiki");
    const [sessionId, setSessionId] = useState("");
    const [sessionToken, setSessionToken] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            await onConnect(baseUrl, sessionId, sessionToken);
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
                    ✅ Connected to Confluence
                </p>
            </div>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div>
                <label className="block text-sm font-medium mb-1">
                    Confluence URL
                </label>
                <input
                    type="url"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://company.atlassian.net/wiki"
                    required
                    className="w-full px-3 py-2 border rounded dark:bg-gray-800"
                />
            </div>

            <div>
                <label className="block text-sm font-medium mb-1">
                    Session ID (JSESSIONID cookie)
                </label>
                <input
                    type="password"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    placeholder="Enter JSESSIONID value"
                    required
                    className="w-full px-3 py-2 border rounded dark:bg-gray-800"
                />
            </div>

            <div>
                <label className="block text-sm font-medium mb-1">
                    Session Token (cloud.session.token cookie)
                </label>
                <input
                    type="password"
                    value={sessionToken}
                    onChange={(e) => setSessionToken(e.target.value)}
                    placeholder="Enter cloud.session.token value"
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
                {loading ? "Connecting..." : "Connect to Confluence"}
            </button>

            <div className="text-xs text-gray-600 dark:text-gray-400">
                <p className="font-medium mb-1">How to get session cookies:</p>
                <ol className="list-decimal list-inside space-y-1">
                    <li>Open Confluence in your browser and log in</li>
                    <li>Open Developer Tools (F12) → Application/Storage → Cookies</li>
                    <li>Find and copy JSESSIONID and cloud.session.token values</li>
                </ol>
            </div>
        </form>
    );
}
