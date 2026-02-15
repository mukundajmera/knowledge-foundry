/* ═══════════════════════════════════════════════════════════
   E2E Test — Accessibility
   Verifies: keyboard navigation, ARIA attributes, focus management
   ═══════════════════════════════════════════════════════════ */

import { test, expect } from "@playwright/test";

test.describe("Accessibility", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/");
    });

    test("query input has proper aria-label", async ({ page }) => {
        const input = page.locator("#query-input");
        await expect(input).toHaveAttribute("aria-label", "Query input");
    });

    test("send button has proper aria-label", async ({ page }) => {
        const sendBtn = page.locator("#send-btn");
        await expect(sendBtn).toHaveAttribute("aria-label", "Send query");
    });

    test("/ key focuses the input", async ({ page }) => {
        // Click body first to ensure no element is focused
        await page.locator("body").click();
        await page.keyboard.press("/");
        const input = page.locator("#query-input");
        await expect(input).toBeFocused();
    });

    test("advanced options toggle has aria-expanded", async ({ page }) => {
        const toggle = page.locator(".advanced-toggle");
        await expect(toggle).toHaveAttribute("aria-expanded", "false");
        await toggle.click();
        await expect(toggle).toHaveAttribute("aria-expanded", "true");
    });

    test("sidebar has navigation role", async ({ page }) => {
        const sidebar = page.locator("aside");
        await expect(sidebar).toHaveAttribute("role", "navigation");
    });

    test("all icon buttons have aria-labels", async ({ page }) => {
        const iconBtns = page.locator(".icon-btn");
        const count = await iconBtns.count();
        for (let i = 0; i < count; i++) {
            const btn = iconBtns.nth(i);
            const label = await btn.getAttribute("aria-label");
            expect(label).toBeTruthy();
        }
    });

    test("page has proper heading hierarchy — single h1", async ({ page }) => {
        const h1s = page.locator("h1");
        const count = await h1s.count();
        expect(count).toBe(1);
    });

    test("page has dark color scheme meta tag", async ({ page }) => {
        const meta = page.locator('meta[name="color-scheme"]');
        await expect(meta).toHaveAttribute("content", "dark");
    });
});
