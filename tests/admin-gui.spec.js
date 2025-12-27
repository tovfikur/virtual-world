// Admin GUI smoke tests
// Uses env tokens TEST_ADMIN_ACCESS_TOKEN / TEST_ADMIN_REFRESH_TOKEN to set session

const { test, expect } = require("@playwright/test");

const ADMIN_PAGES = [
  {
    path: "/admin/security",
    check: async (page) => {
      await expect(page.getByText("Security Dashboard")).toBeVisible();
      await page.getByRole("button", { name: "IP Controls" }).click();
      await expect(
        page.getByRole("heading", { name: "Blocked IPs" })
      ).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "Whitelisted IPs" })
      ).toBeVisible();
    },
  },
  {
    path: "/admin/maintenance",
    check: async (page) => {
      await expect(page.getByText("Maintenance & Operations")).toBeVisible();
      await expect(page.getByRole("button", { name: "VACUUM" })).toBeVisible();
      await expect(page.getByRole("button", { name: "ANALYZE" })).toBeVisible();
      await expect(page.getByRole("button", { name: "REINDEX" })).toBeVisible();
    },
  },
  {
    path: "/admin/analytics",
    check: async (page) => {
      await expect(page.getByText("Analytics & Reporting")).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Export CSV" }).first()
      ).toBeVisible();
    },
  },
  {
    path: "/admin/logs",
    check: async (page) => {
      await expect(page.getByText("Audit Logs")).toBeVisible();
      await expect(page.getByText("Log Level")).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Export Current View (CSV)" })
      ).toBeVisible();
    },
  },
];

// Helper to set tokens from env
async function setTokens(page) {
  const access = process.env.TEST_ADMIN_ACCESS_TOKEN;
  const refresh = process.env.TEST_ADMIN_REFRESH_TOKEN;
  if (!access) {
    test.skip(
      true,
      "Admin access token not provided (TEST_ADMIN_ACCESS_TOKEN)"
    );
  }
  await page.addInitScript(
    ({ access, refresh }) => {
      window.localStorage.setItem("access_token", access);
      if (refresh) {
        window.localStorage.setItem("refresh_token", refresh);
      }
    },
    { access, refresh }
  );
}

for (const cfg of ADMIN_PAGES) {
  test(`Admin GUI: ${cfg.path} smoke`, async ({ page }, testInfo) => {
    await setTokens(page);
    await page.goto(cfg.path);
    await cfg.check(page);
    await page.screenshot({
      path: testInfo.outputPath(
        `screenshot-${cfg.path.replace(/\W+/g, "-")}.png`
      ),
      fullPage: true,
    });
  });
}
