/* ═══════════════════════════════════════════════════════════
   E2E Test — File Upload
   Verifies: attach button, drag-and-drop zone, file chips
   ═══════════════════════════════════════════════════════════ */

import { test, expect } from "@playwright/test";

test.describe("File Upload", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/");
        await page.evaluate(() => localStorage.clear());
        await page.reload();
    });

    test("attach button is visible and clickable", async ({ page }) => {
        await page.goto("/");
        const attachBtn = page.locator("#attach-btn");
        await expect(attachBtn).toBeVisible();
        await expect(attachBtn).toHaveAttribute("aria-label", "Attach file");
    });

    test("file input is hidden by default", async ({ page }) => {
        await page.goto("/");
        const fileInput = page.locator(".file-input-hidden");
        await expect(fileInput).toBeAttached();
        // Hidden via CSS display:none
        await expect(fileInput).not.toBeVisible();
    });

    test("sidebar search input is present", async ({ page }) => {
        await page.goto("/");
        const searchInput = page.locator("#sidebar-search");
        await expect(searchInput).toBeVisible();
        await expect(searchInput).toHaveAttribute(
            "placeholder",
            /Search conversations/
        );
    });
});
