/* ═══════════════════════════════════════════════════════════
   E2E Test — Sidebar / Conversation History
   Verifies: new chat button, conversation list rendering
   ═══════════════════════════════════════════════════════════ */

import { test, expect } from "@playwright/test";

test.describe("Sidebar", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/");
        await page.evaluate(() => localStorage.clear());
        await page.reload();
    });

    test("shows new chat button", async ({ page }) => {
        await page.goto("/");
        const newChatBtn = page.locator("#new-chat-btn");
        await expect(newChatBtn).toBeVisible();
        await expect(newChatBtn).toContainText("New conversation");
    });

    test("clicking new chat creates a conversation", async ({ page }) => {
        await page.goto("/");
        const newChatBtn = page.locator("#new-chat-btn");
        await newChatBtn.click();
        // Should have at least one conversation item
        const items = page.locator(".conversation-item");
        await expect(items.first()).toBeVisible({ timeout: 2000 });
    });

    test("sidebar has correct aria role", async ({ page }) => {
        await page.goto("/");
        const sidebar = page.locator("aside[role='navigation']");
        await expect(sidebar).toBeVisible();
    });
});
