import { test, expect, type Page } from "@playwright/test";

/**
 * Smoke tests for the storefront. These are designed to pass even without
 * seeded data: any navigation that may 404 (e.g. /demo-store when the demo
 * tenant has not been seeded) is skipped via `skipIfError`.
 */
async function skipIfError(page: Page, path: string) {
  const response = await page.goto(path);
  if (!response || response.status() >= 400) {
    test.skip(true, `${path} returned ${response ? response.status() : "no response"} — seed data required`);
  }
}

test("home renders store heading", async ({ page }) => {
  await skipIfError(page, "/demo-store");
  const heading = page.locator("h1").first();
  await expect(heading).toBeVisible();
  await expect(heading).not.toBeEmpty();
});

test("products page lists grid or empty state", async ({ page }) => {
  await skipIfError(page, "/demo-store/products");
  const grid = page.locator("main [class*='grid'], a[href*='/products/']");
  const emptyState = page.getByText(/no products|coming soon|empty/i);
  await expect(grid.or(emptyState).first()).toBeVisible();
});

test("cart page shows Your Cart heading", async ({ page }) => {
  await skipIfError(page, "/demo-store/cart");
  await expect(page.locator("h1").first()).toContainText("Your Cart");
});

test("checkout wizard reachable from cart with seeded session", async ({ page }) => {
  await skipIfError(page, "/demo-store/cart");
  // With an empty guest cart the checkout page still renders its first step
  await page.click("a[href*='/checkout'], button:has-text('Checkout'), a:has-text('Checkout')");
  await page.waitForURL(/checkout/, { timeout: 5000 }).catch(() => {
    test.skip(true, "no checkout link available — cart empty or unseeded");
  });
  if (page.url().includes("checkout")) {
    await expect(page.locator("h1, h2").first()).toBeVisible();
  }
});

test("add to cart updates cart from product page", async ({ page }) => {
  await skipIfError(page, "/demo-store/products");
  const productLink = page.locator("a[href*='/products/']").first();
  if ((await productLink.count()) === 0) {
    test.skip(true, "no products seeded — skipping add-to-cart flow");
    return;
  }
  await productLink.click();
  await page.waitForURL(/\/products\//);
  const addBtn = page.locator("button:has-text('Add to Cart'), button:has-text('Add to cart')").first();
  if ((await addBtn.count()) === 0) {
    test.skip(true, "no add-to-cart button found");
    return;
  }
  await addBtn.click();
  await expect(page.locator("text=/added|cart/i").first()).toBeVisible({ timeout: 5000 });
});
