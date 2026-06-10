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
    // v6 Phase C: / → 307 /zh, sidebar 仍是中文(默认 locale)
    await page.goto("/zh/");
    // Sidebar nav link(更宽松的 selector,因为 next-intl 文本在嵌套 span 里)
    const writeLink = page.locator("nav a").filter({ hasText: "写作工作台" });
    await expect(writeLink).toBeVisible({ timeout: 10_000 });
    await writeLink.click();
    // 跳转到 /zh/write(middleware 重写,URL 保留 /zh/ 前缀)
    await expect(page).toHaveURL(/\/(zh|)\/write\/?$/);
  });
});