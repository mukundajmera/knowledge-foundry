/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Local Models Page
   Page for discovering and managing local LLM models
   ═══════════════════════════════════════════════════════════ */

import LocalProviderDiscovery from "@/components/models/LocalProviderDiscovery";

export default function LocalModelsPage() {
    return (
        <div className="container mx-auto p-6">
            <div className="mb-6">
                <h1 className="text-3xl font-bold mb-2">Local Models</h1>
                <p className="text-gray-600 dark:text-gray-400">
                    Discover and use locally-running LLM models from Ollama and LM Studio.
                    Zero cost, full privacy.
                </p>
            </div>

            <LocalProviderDiscovery />
        </div>
    );
}
