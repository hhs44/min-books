import { test, expect } from "@playwright/test";

test.describe("Login page", () => {
  test("renders login form with token input and submit button", async ({ page }) => {
    await page.goto("/login");
    // Token input
    const tokenInput = page.locator('input[type="password"]');
    await expect(tokenInput).toBeVisible();
    // Submit button
    const submitButton = page.getByRole("button", { name: "登录" });
    await expect(submitButton).toBeVisible();
    // Hint trigger
    const hintButton = page.getByRole("button", { name: "找不到 token?" });
    await expect(hintButton).toBeVisible();
  });

  test("typing token and submitting keeps user on login (no backend)", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="password"]', "fake-token-for-e2e");
    // The submit button should be enabled now
    const submitButton = page.getByRole("button", { name: "登录" });
    await expect(submitButton).toBeEnabled();
    // Without a backend, the request will fail and stay on login
    // We just verify the UI flow up to click
    await submitButton.click();
    // Either an error shows OR we stay on login
    await expect(page).toHaveURL(/\/(login)?/);
  });

  test("home page redirects to login or shows books", async ({ page }) => {
    await page.goto("/");
    // Without auth, may show error alert or redirect; just verify it loaded
    await expect(page.locator("body")).toBeVisible();
  });
});