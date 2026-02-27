import { test, expect } from "@playwright/test";

test.describe("Complete User Journey", () => {
    test("user can chat and view responses", async ({ page }) => {
        // 1. Visit homepage
        await page.goto("/");
        await expect(page.locator("h1")).toContainText("Knowledge Foundry");

        // Mock the API response to avoid hitting external LLMs (which fail without keys)
        await page.route("**/v1/query", async (route) => {
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    answer: "Machine learning is a subset of artificial intelligence.",
                    citations: [],
                    routing: null,
                    performance: null,
                }),
            });
        });

        // 2. Send first query
        const input = page.locator("#query-input");
        await input.fill("What is machine learning?");
        // Wait for send button to be enabled
        const sendBtn = page.locator("#send-btn");
        await expect(sendBtn).toBeEnabled();
        await sendBtn.click();

        // 3. Wait for response bubble (user message first, then AI)
        // User message
        await expect(page.locator(".message").filter({ hasText: "What is machine learning?" })).toBeVisible();

        // AI message (might take a moment to stream)
        // Look for the AI message container which usually comes after
        const aiMessage = page.locator(".message:has(.message-avatar.ai)").last();
        await expect(aiMessage).toBeVisible({ timeout: 10000 });

        // 4. Verify AI responding (wait for some text)
        await expect(aiMessage).not.toBeEmpty();
    });

    test("advanced options toggle", async ({ page }) => {
        await page.goto("/");

        // Toggle advanced
        const advToggle = page.locator("button:has-text('Advanced')");
        if (await advToggle.isVisible()) {
            await advToggle.click();
            await expect(page.locator(".advanced-panel")).toBeVisible();
            await expect(page.locator("select")).toBeVisible(); // Model selector
        }
    });

    test("theme toggle works", async ({ page }) => {
        await page.goto("/");

        // Find theme toggle by its stable ID
        const themeBtn = page.locator("#theme-toggle-btn");
        await expect(themeBtn).toBeVisible({ timeout: 5000 });

        // Check initial theme and verify it changes after click
        const initialTheme = await page.locator("html").getAttribute("data-theme");
        await themeBtn.click();
        const newTheme = await page.locator("html").getAttribute("data-theme");
        expect(newTheme).not.toBe(initialTheme);
    });
});
