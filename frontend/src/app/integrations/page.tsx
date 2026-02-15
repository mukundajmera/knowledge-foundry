/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Integrations Page
   Page for managing Atlassian integrations
   ═══════════════════════════════════════════════════════════ */

import AtlassianIntegration from "@/components/integrations/AtlassianIntegration";

export default function IntegrationsPage() {
    return (
        <div className="container mx-auto p-6">
            <div className="mb-6">
                <h1 className="text-3xl font-bold mb-2">Integrations</h1>
                <p className="text-gray-600 dark:text-gray-400">
                    Connect Knowledge Foundry to your Atlassian tools (Confluence, Jira, Bitbucket).
                </p>
            </div>

            <AtlassianIntegration />
        </div>
    );
}
