/* ═══════════════════════════════════════════════════════════
   E2E Test — Export Flow
   Verifies: export modal, format selection, export generation
   ═══════════════════════════════════════════════════════════ */

import { test, expect } from "@playwright/test";

test.describe("Export System", () => {
    test.beforeEach(async ({ page }) => {
        // Set up a conversation in localStorage before each test
        await page.goto("/");
        await page.evaluate(() => {
            const conversation = {
                id: "conv_test_001",
                title: "Test Conversation for Export",
                messages: [
                    {
                        id: "msg_001",
                        role: "user",
                        content: "What is Python?",
                        timestamp: Date.now() - 60000,
                    },
                    {
                        id: "msg_002",
                        role: "assistant",
                        content: "Python is a high-level programming language known for its simplicity and readability.",
                        timestamp: Date.now(),
                        citations: [
                            {
                                document_id: "doc_001",
                                title: "Python Documentation",
                                relevance_score: 0.95,
                            },
                        ],
                        model: "sonnet",
                        confidence: 0.92,
                    },
                ],
                createdAt: Date.now() - 60000,
                updatedAt: Date.now(),
            };
            localStorage.setItem("kf_conversations", JSON.stringify([conversation]));
        });
        await page.reload();
    });

    test("export conversation button is visible when there are messages", async ({ page }) => {
        await page.goto("/");
        // Wait for conversation to load
        await expect(page.locator(".messages-list")).toBeVisible();
        // Check export button is visible
        await expect(page.locator("#export-conversation-btn")).toBeVisible();
    });

    test("export modal opens when clicking export conversation button", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Click export button
        await page.locator("#export-conversation-btn").click();

        // Check modal is visible
        await expect(page.locator(".export-modal")).toBeVisible();
        await expect(page.locator("#export-modal-title")).toContainText("Export");
    });

    test("export modal shows available formats", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Open export modal
        await page.locator("#export-conversation-btn").click();
        await expect(page.locator(".export-modal")).toBeVisible();

        // Wait for formats to load
        await page.waitForSelector(".export-formats", { timeout: 10000 });

        // Check that format buttons are present
        const formatButtons = page.locator(".format-btn");
        const count = await formatButtons.count();
        expect(count).toBeGreaterThanOrEqual(1);
    });

    test("export modal can be closed", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Open export modal
        await page.locator("#export-conversation-btn").click();
        await expect(page.locator(".export-modal")).toBeVisible();

        // Close modal using close button
        await page.locator(".modal-close-btn").click();
        await expect(page.locator(".export-modal")).not.toBeVisible();
    });

    test("export modal closes when clicking overlay", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Open export modal
        await page.locator("#export-conversation-btn").click();
        await expect(page.locator(".export-modal")).toBeVisible();

        // Click on overlay (outside modal content)
        await page.locator(".modal-overlay").click({ position: { x: 10, y: 10 } });
        await expect(page.locator(".export-modal")).not.toBeVisible();
    });

    test("export options can be toggled", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Open export modal
        await page.locator("#export-conversation-btn").click();
        await expect(page.locator(".export-modal")).toBeVisible();

        // Wait for formats to load
        await page.waitForSelector(".export-options", { timeout: 10000 });

        // Toggle include metadata option
        const metadataCheckbox = page.locator('input[type="checkbox"]').first();
        await expect(metadataCheckbox).toBeChecked();
        await metadataCheckbox.click();
        await expect(metadataCheckbox).not.toBeChecked();
    });

    test("message export button is visible on assistant messages", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Check for export button on message
        const exportMessageBtn = page.locator("#export-message-btn").first();
        await expect(exportMessageBtn).toBeVisible();
    });

    test("message export modal opens from message action", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Click export button on message
        const exportMessageBtn = page.locator("#export-message-btn").first();
        await exportMessageBtn.click();

        // Check modal is visible
        await expect(page.locator(".export-modal")).toBeVisible();
        await expect(page.locator("#export-modal-title")).toContainText("Export Message");
    });

    test("format selection updates selected state", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Open export modal
        await page.locator("#export-conversation-btn").click();
        await expect(page.locator(".export-modal")).toBeVisible();

        // Wait for formats to load
        await page.waitForSelector(".export-formats", { timeout: 10000 });

        // Click on a format button (e.g., HTML)
        const formatButtons = page.locator(".format-btn");
        const secondFormat = formatButtons.nth(1);
        await secondFormat.click();

        // Check it has selected class
        await expect(secondFormat).toHaveClass(/selected/);
    });

    test("export button is enabled after formats load", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".messages-list")).toBeVisible();

        // Open export modal
        await page.locator("#export-conversation-btn").click();
        await expect(page.locator(".export-modal")).toBeVisible();

        // Wait for formats to load
        await page.waitForSelector(".export-formats", { timeout: 10000 });

        // Check export button is enabled
        const exportBtn = page.locator("#export-generate-btn");
        await expect(exportBtn).toBeEnabled();
    });
});
