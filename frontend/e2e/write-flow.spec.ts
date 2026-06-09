import { test, expect } from "@playwright/test";

test.describe("Write workbench", () => {
  test("renders write page with form", async ({ page }) => {
    await page.goto("/write");
    // Heading
    await expect(page.getByRole("heading", { name: "写作工作台" })).toBeVisible();
    // Chapter number input
    const chapterInput = page.locator('input[type="number"]');
    await expect(chapterInput).toBeVisible();
    // Textarea for focus
    await expect(page.locator("textarea")).toBeVisible();
    // Submit button (initially disabled because no bookId/focus)
    const startButton = page.getByRole("button", { name: /开始写/ });
    await expect(startButton).toBeVisible();
    await expect(startButton).toBeDisabled();
  });

  test("typing focus enables start button when bookId present", async ({ page }) => {
    await page.goto("/write?bookId=test-book-id");
    const textarea = page.locator("textarea");
    await textarea.fill("本章主角遇到神秘老人");
    // After typing, button should be enabled
    const startButton = page.getByRole("button", { name: /开始写/ });
    await expect(startButton).toBeEnabled();
  });

  test("navigation to write via sidebar works", async ({ page }) => {
    await page.goto("/");
    // Sidebar nav link
    const writeLink = page.getByRole("link", { name: "写作工作台" });
    await expect(writeLink).toBeVisible();
    await writeLink.click();
    await expect(page).toHaveURL("/write");
  });
});