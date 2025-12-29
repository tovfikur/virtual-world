// Playwright admin GUI test using login form and demo credentials
const { test, expect } = require("@playwright/test");

const ADMIN_PAGES = [
  {
    path: "/admin/security",
    check: async (page) => {
      await expect(page.getByText("Security Dashboard")).toBeVisible();
    },
  },
  {
    path: "/admin/maintenance",
    check: async (page) => {
      await expect(page.getByText("Maintenance & Operations")).toBeVisible();
    },
  },
  {
    path: "/admin/analytics",
    check: async (page) => {
      await expect(page.getByText("Analytics & Reporting")).toBeVisible();
    },
  },
  {
    path: "/admin/logs",
    check: async (page) => {
      await expect(page.getByText("Audit Logs")).toBeVisible();
    },
  },
];

test.describe("Admin GUI via Login", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("http://localhost/login");
    await page.fill('input[type="email"]', "demo@example.com");
    await page.fill('input[type="password"]', "DemoPassword123!");
    await Promise.all([
      page.waitForNavigation({ url: /\/world|\/admin/ }),
      page.click('button[type="submit"]'),
    ]);
    // Confirm HUD/navbar is present after login
    await expect(page.locator("nav")).toBeVisible();
  });

  for (const cfg of ADMIN_PAGES) {
    test(`Admin page ${cfg.path} shows HUD and content`, async ({ page }) => {
      await page.goto(`http://localhost${cfg.path}`);
      // Check HUD/navbar is present
      await expect(page.locator("nav")).toBeVisible();
      // Check page-specific content
      await cfg.check(page);
    });
  }
});
