/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Bitbucket Authentication Component
   App password authentication for Bitbucket integration
   ═══════════════════════════════════════════════════════════ */

"use client";

import { useState } from "react";

interface BitbucketAuthProps {
    onConnect: (workspace: string, username: string, appPassword: string) => Promise<void>;
    isConnected: boolean;
}

export default function BitbucketAuth({ onConnect, isConnected }: BitbucketAuthProps) {
    const [workspace, setWorkspace] = useState("");
    const [username, setUsername] = useState("");
    const [appPassword, setAppPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            await onConnect(workspace, username, appPassword);
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
                    ✅ Connected to Bitbucket
                </p>
            </div>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div>
                <label className="block text-sm font-medium mb-1">
                    Workspace
                </label>
                <input
                    type="text"
                    value={workspace}
                    onChange={(e) => setWorkspace(e.target.value)}
                    placeholder="myworkspace"
                    required
                    className="w-full px-3 py-2 border rounded dark:bg-gray-800"
                />
            </div>

            <div>
                <label className="block text-sm font-medium mb-1">
                    Username
                </label>
                <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="myusername"
                    required
                    className="w-full px-3 py-2 border rounded dark:bg-gray-800"
                />
            </div>

            <div>
                <label className="block text-sm font-medium mb-1">
                    App Password
                </label>
                <input
                    type="password"
                    value={appPassword}
                    onChange={(e) => setAppPassword(e.target.value)}
                    placeholder="Enter your Bitbucket app password"
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
                {loading ? "Connecting..." : "Connect to Bitbucket"}
            </button>

            <div className="text-xs text-gray-600 dark:text-gray-400">
                <p className="font-medium mb-1">How to create an app password:</p>
                <ol className="list-decimal list-inside space-y-1">
                    <li>Go to Bitbucket → Personal settings → App passwords</li>
                    <li>Click &quot;Create app password&quot;</li>
                    <li>Give it a label and select permissions (repositories: read)</li>
                    <li>Copy the generated password</li>
                </ol>
            </div>
        </form>
    );
}
