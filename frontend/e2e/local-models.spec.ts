/* ═══════════════════════════════════════════════════════════
   Knowledge Foundry — Local Models E2E Tests
   End-to-end tests for local model discovery and management
   ═══════════════════════════════════════════════════════════ */

import { test, expect } from "@playwright/test";

test.describe("Local Models Discovery", () => {
    test("should display local models page", async ({ page }) => {
        await page.goto("/models");

        // Check page title
        await expect(page.getByRole("heading", { name: "Local Models" })).toBeVisible();
        await expect(page.getByText("Discover and use locally-running LLM models")).toBeVisible();
    });

    test("should discover and display local providers", async ({ page }) => {
        // Mock API to return provider data since backend may not be running
        await page.route("**/api/models/local/discover", async (route) => {
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    available_providers: [],
                    ollama: {
                        provider: "ollama",
                        available: false,
                        error: "Not running",
                        models: [],
                        count: 0,
                    },
                    lmstudio: {
                        provider: "lmstudio",
                        available: false,
                        error: "Not running",
                        models: [],
                        count: 0,
                    },
                }),
            });
        });

        await page.goto("/models");

        // Wait for discovery component to load
        await expect(page.getByText("Local LLM Providers")).toBeVisible();

        // Check that both provider cards are displayed
        await expect(page.getByRole("heading", { name: /Ollama/ })).toBeVisible();
        await expect(page.getByRole("heading", { name: /LM Studio/ })).toBeVisible();

        // Check port numbers are displayed
        await expect(page.getByText("Port 11434")).toBeVisible();
        await expect(page.getByText("Port 1234")).toBeVisible();
    });

    test("should show offline status when providers are not running", async ({ page }) => {
        // Mock API to return offline providers
        await page.route("**/api/models/local/discover", async (route) => {
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    available_providers: [],
                    ollama: {
                        provider: "ollama",
                        available: false,
                        error: "Ollama not running on http://localhost:11434",
                        models: [],
                        count: 0,
                    },
                    lmstudio: {
                        provider: "lmstudio",
                        available: false,
                        error: "LMStudio not running on http://localhost:1234/v1",
                        models: [],
                        count: 0,
                    },
                }),
            });
        });

        await page.goto("/models");

        // Wait for discovery
        await expect(page.getByText("Not Detected")).toHaveCount(2);

        // Check warning message
        await expect(
            page.getByText("No local providers detected. Install Ollama or LM Studio")
        ).toBeVisible();
    });

    test("should show online status and models when provider is running", async ({ page }) => {
        // Mock API to return online Ollama with models
        await page.route("**/api/models/local/discover", async (route) => {
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    available_providers: ["ollama"],
                    ollama: {
                        provider: "ollama",
                        available: true,
                        models: [
                            {
                                id: "llama3:8b",
                                name: "llama3:8b",
                                displayName: "Llama 3 8B",
                                family: "llama",
                                parameters: "8B",
                                local: true,
                            },
                            {
                                id: "mistral:7b",
                                name: "mistral:7b",
                                displayName: "Mistral 7B",
                                family: "mistral",
                                parameters: "7B",
                                local: true,
                            },
                        ],
                        count: 2,
                    },
                    lmstudio: {
                        provider: "lmstudio",
                        available: false,
                        error: "LMStudio not running",
                        models: [],
                        count: 0,
                    },
                }),
            });
        });

        await page.goto("/models");

        // Check Ollama is running
        await expect(page.getByText("Running • 2 models available")).toBeVisible();

        // Check models are listed
        await expect(page.getByText("• Llama 3 8B")).toBeVisible();
        await expect(page.getByText("• Mistral 7B")).toBeVisible();
    });

    test("should show setup instructions modal when clicking setup button", async ({ page }) => {
        // Mock offline providers
        await page.route("**/api/models/local/discover", async (route) => {
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    available_providers: [],
                    ollama: {
                        provider: "ollama",
                        available: false,
                        error: "Not running",
                        models: [],
                        count: 0,
                    },
                    lmstudio: {
                        provider: "lmstudio",
                        available: false,
                        error: "Not running",
                        models: [],
                        count: 0,
                    },
                }),
            });
        });

        await page.goto("/models");

        // Click setup instructions for Ollama
        await page.getByText("View setup instructions").first().click();

        // Check modal is displayed
        await expect(page.getByRole("heading", { name: "Install Ollama" })).toBeVisible();
        await expect(page.getByText("Visit https://ollama.ai")).toBeVisible();
        await expect(page.getByRole("link", { name: "Visit Website" })).toBeVisible();

        // Close modal
        await page.getByRole("button", { name: "Close" }).click();
        await expect(page.getByRole("heading", { name: "Install Ollama" })).not.toBeVisible();
    });

    test("should refresh provider status when clicking refresh button", async ({ page }) => {
        let requestCount = 0;

        await page.route("**/api/models/local/discover", async (route) => {
            requestCount++;
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    available_providers: [],
                    ollama: {
                        provider: "ollama",
                        available: false,
                        error: "Not running",
                        models: [],
                        count: 0,
                    },
                    lmstudio: {
                        provider: "lmstudio",
                        available: false,
                        error: "Not running",
                        models: [],
                        count: 0,
                    },
                }),
            });
        });

        await page.goto("/models");
        await page.waitForLoadState("networkidle");

        const initialCount = requestCount;

        // Click refresh button
        await page.getByRole("button", { name: "Refresh" }).click();
        await page.waitForTimeout(500);

        // Verify another request was made
        expect(requestCount).toBe(initialCount + 1);
    });
});
