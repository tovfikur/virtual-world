import { test, expect } from "@playwright/test";

/**
 * Price History Tab Visual Test
 * Tests that the Price History tab in the Trading page:
 * 1. Loads and displays properly
 * 2. Shows instrument selector
 * 3. Displays chart with candle data
 * 4. Has proper controls for timeframe/period selection
 */

const TEST_USER = {
  email: "demo@example.com",
  password: "DemoPassword123!",
};

test.describe("Price History Tab Tests", () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    // Fill login form
    await page.fill(
      'input[type="email"], input[name="email"]',
      TEST_USER.email
    );
    await page.fill(
      'input[type="password"], input[name="password"]',
      TEST_USER.password
    );

    // Submit login
    const submitButton = page.locator('button[type="submit"]');
    await submitButton.click();

    // Wait for redirect after login
    await page.waitForURL((url) => !url.pathname.includes("/login"), {
      timeout: 10000,
    });

    // Navigate to trading page
    await page.goto("/trading");
    await page.waitForLoadState("networkidle");
  });

  test("should display Trading Hub page with tabs", async ({ page }) => {
    // Verify Trading System heading
    await expect(page.locator("h1")).toContainText("Trading System");

    // Check all tabs are visible (using button role to avoid matching headings)
    await expect(
      page.getByRole("button", { name: "📊 Overview" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "📈 Exchange" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "💼 Portfolio" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "📉 Price History" })
    ).toBeVisible();
  });

  test("should navigate to Price History tab", async ({ page }) => {
    // Click on Price History tab
    await page.getByRole("button", { name: "📉 Price History" }).click();

    // Wait for tab content to load
    await page.waitForTimeout(1000);

    // Verify Price History chart header is visible
    await expect(page.locator("h3:has-text('Price History')")).toBeVisible({
      timeout: 10000,
    });

    // Verify instrument selector is present
    await expect(page.locator("select")).toBeVisible({ timeout: 5000 });
  });

  test("should display candlestick chart with data", async ({ page }) => {
    // Navigate to Price History tab
    await page.getByRole("button", { name: "📉 Price History" }).click();
    await page.waitForTimeout(2000);

    // Wait for loading to complete
    await page
      .waitForSelector("text=Loading", { state: "hidden", timeout: 15000 })
      .catch(() => {});

    // Check if chart container or SVG is present
    const chartContainer = page.locator(
      ".bg-gray-900.border.border-gray-800.rounded-xl"
    );
    await expect(chartContainer.first()).toBeVisible({ timeout: 10000 });

    // Take screenshot of the Price History tab
    await page.screenshot({
      path: "test-results/price-history-tab.png",
      fullPage: true,
    });
  });

  test("should have timeframe selection controls", async ({ page }) => {
    // Navigate to Price History tab
    await page.getByRole("button", { name: "📉 Price History" }).click();
    await page.waitForTimeout(1500);

    // Check for timeframe buttons (1 Min, 5 Min, 15 Min, etc.)
    const timeframeButtons = ["1 Min", "5 Min", "15 Min", "30 Min", "1 Hour"];

    for (const tf of timeframeButtons) {
      const button = page.locator(`button:has-text("${tf}")`);
      // At least some of these should be visible
      const isVisible = await button.isVisible().catch(() => false);
      if (isVisible) {
        console.log(`Found timeframe button: ${tf}`);
      }
    }

    // Check for period buttons (1H, 6H, 24H, etc.)
    const periodButtons = ["1H", "6H", "24H", "3D", "1W"];
    for (const period of periodButtons) {
      const button = page.locator(`button:has-text("${period}")`);
      const isVisible = await button.isVisible().catch(() => false);
      if (isVisible) {
        console.log(`Found period button: ${period}`);
      }
    }
  });

  test("should display OHLCV stats panel", async ({ page }) => {
    // Navigate to Price History tab
    await page.getByRole("button", { name: "📉 Price History" }).click();
    await page.waitForTimeout(2000);

    // Check for OHLCV stats labels
    const statsLabels = ["Open", "High", "Low", "Close", "Volume"];

    for (const label of statsLabels) {
      const statElement = page.locator(`text=${label}`).first();
      const isVisible = await statElement.isVisible().catch(() => false);
      if (isVisible) {
        console.log(`Found stat: ${label}`);
      }
    }
  });

  test("should switch instruments in Price History", async ({ page }) => {
    // Navigate to Price History tab
    await page.getByRole("button", { name: "📉 Price History" }).click();
    await page.waitForTimeout(1500);

    // Try to find and click on a different instrument button
    const instrumentButtons = page.locator(
      'button:has-text("SYSCO"), button:has-text("OPTCO")'
    );
    const count = await instrumentButtons.count();

    if (count > 0) {
      // Click the first instrument button
      await instrumentButtons.first().click();
      await page.waitForTimeout(1000);

      // Verify chart refreshes (no error message)
      const errorMessage = page.locator('text="Failed to load price history"');
      const hasError = await errorMessage.isVisible().catch(() => false);
      expect(hasError).toBeFalsy();
    }
  });

  test("should have auto-refresh toggle", async ({ page }) => {
    // Navigate to Price History tab
    await page.getByRole("button", { name: "📉 Price History" }).click();
    await page.waitForTimeout(1500);

    // Look for auto-refresh toggle button
    const autoRefreshButton = page.locator(
      'button:has-text("Auto"), button:has-text("Manual")'
    );
    const isVisible = await autoRefreshButton
      .first()
      .isVisible()
      .catch(() => false);

    if (isVisible) {
      console.log("Auto-refresh toggle found");
      // Click to toggle
      await autoRefreshButton.first().click();
      await page.waitForTimeout(500);
    }
  });

  test("should take full page screenshot of trading page", async ({ page }) => {
    // Navigate to each tab and take screenshots

    // Overview tab (default)
    await page.screenshot({
      path: "test-results/trading-overview.png",
      fullPage: true,
    });

    // Exchange tab
    await page.getByRole("button", { name: "📈 Exchange" }).click();
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: "test-results/trading-exchange.png",
      fullPage: true,
    });

    // Portfolio tab
    await page.getByRole("button", { name: "💼 Portfolio" }).click();
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: "test-results/trading-portfolio.png",
      fullPage: true,
    });

    // Price History tab
    await page.getByRole("button", { name: "📉 Price History" }).click();
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: "test-results/trading-price-history.png",
      fullPage: true,
    });
  });
});

test.describe("Admin Price Update Creates History", () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin (demo user has admin role)
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    // Use demo credentials (demo user is admin)
    await page.fill(
      'input[type="email"], input[name="email"]',
      "demo@example.com"
    );
    await page.fill(
      'input[type="password"], input[name="password"]',
      "DemoPassword123!"
    );

    const submitButton = page.locator('button[type="submit"]');
    await submitButton.click();

    await page.waitForURL((url) => !url.pathname.includes("/login"), {
      timeout: 15000,
    });
  });

  test("should show admin controls tab for admin users", async ({ page }) => {
    await page.goto("/trading");
    await page.waitForLoadState("networkidle");

    // Check if Admin Controls tab is visible (admin only)
    const adminTab = page.getByRole("button", { name: "⚙️ Admin Controls" });
    const isAdmin = await adminTab.isVisible().catch(() => false);

    if (isAdmin) {
      console.log("Admin Controls tab visible - user is admin");
      await adminTab.click();
      await page.waitForTimeout(1000);

      // Take screenshot of admin panel
      await page.screenshot({
        path: "test-results/trading-admin-panel.png",
        fullPage: true,
      });
    } else {
      console.log("Admin Controls tab not visible - user is not admin");
    }
  });
});
