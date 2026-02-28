/* ═══════════════════════════════════════════════════════════
   E2E Test — Chat Flow
   Verifies: page load, welcome screen, send query, message rendering
   ═══════════════════════════════════════════════════════════ */

import { test, expect } from "@playwright/test";

test.describe("Chat Interface", () => {
    test.beforeEach(async ({ page }) => {
        // Clear localStorage to start fresh
        await page.goto("/");
        await page.evaluate(() => localStorage.clear());
        await page.reload();
    });

    test("displays welcome screen on first visit", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".welcome-title")).toBeVisible();
        await expect(page.locator(".welcome-title")).toHaveText("Knowledge Foundry");
        await expect(page.locator(".welcome-subtitle")).toContainText("enterprise AI");
    });

    test("has a query input field", async ({ page }) => {
        await page.goto("/");
        const input = page.locator("#query-input");
        await expect(input).toBeVisible();
        await expect(input).toHaveAttribute(
            "placeholder",
            /Ask a question/
        );
    });

    test("send button is disabled when input is empty", async ({ page }) => {
        await page.goto("/");
        const sendBtn = page.locator("#send-btn");
        await expect(sendBtn).toBeDisabled();
    });

    test("send button enables when text is entered", async ({ page }) => {
        await page.goto("/");
        const input = page.locator("#query-input");
        await input.fill("What is our security policy?");
        const sendBtn = page.locator("#send-btn");
        await expect(sendBtn).toBeEnabled();
    });

    test("displays suggestion chips", async ({ page }) => {
        await page.goto("/");
        const chips = page.locator(".suggestion-chip");
        await expect(chips.first()).toBeVisible();
        const count = await chips.count();
        expect(count).toBeGreaterThanOrEqual(1);
    });

    test("clicking suggestion fills query input", async ({ page }) => {
        await page.goto("/");
        const chip = page.locator(".suggestion-chip").first();
        const chipText = await chip.textContent();
        await chip.click();
        const input = page.locator("#query-input");
        // The chip text includes the "💡 " prefix
        const expectedText = chipText?.replace("💡 ", "").trim();
        await expect(input).toHaveValue(expectedText || "");
    });

    test("header shows logo and navigation", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator(".header-logo")).toContainText("Knowledge Foundry");
        await expect(page.locator(".header-actions")).toBeVisible();
    });

    test("keyboard shortcuts modal opens on ? key", async ({ page }) => {
        await page.goto("/");
        // Wait for page to fully hydrate before sending keyboard events
        await page.waitForSelector("#shortcuts-btn", { state: "visible" });
        await page.keyboard.press("?");
        await expect(page.locator(".shortcuts-modal")).toBeVisible();
        await expect(page.locator(".shortcuts-title")).toContainText("Keyboard Shortcuts");
        // Close on Esc
        await page.keyboard.press("Escape");
        await expect(page.locator(".shortcuts-modal")).not.toBeVisible();
    });

    test("keyboard shortcuts modal opens from header button", async ({ page }) => {
        await page.goto("/");
        await page.locator("#shortcuts-btn").click();
        await expect(page.locator(".shortcuts-modal")).toBeVisible();
    });

    test("advanced options panel toggles", async ({ page }) => {
        await page.goto("/");
        const toggle = page.locator(".advanced-toggle");
        await expect(toggle).toBeVisible();
        await toggle.click();
        await expect(page.locator(".advanced-panel")).toBeVisible();
        await expect(page.locator("#model-select")).toBeVisible();
        // Toggle off
        await toggle.click();
        await expect(page.locator(".advanced-panel")).not.toBeVisible();
    });

    test("attach button is visible", async ({ page }) => {
        await page.goto("/");
        await expect(page.locator("#attach-btn")).toBeVisible();
    });
});
