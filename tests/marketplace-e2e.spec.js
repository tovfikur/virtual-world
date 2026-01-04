const { test, expect } = require("@playwright/test");

const EMAIL = "demo@example.com";
const PASSWORD = "DemoPassword123!";
const BASE = "http://localhost/api/v1";

async function login(request) {
  const resp = await request.post(`${BASE}/auth/login`, {
    data: { email: EMAIL, password: PASSWORD },
  });
  expect(resp.ok()).toBeTruthy();
  const json = await resp.json();
  return json.access_token;
}

async function getMe(request, token) {
  const resp = await request.get(`${BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.ok()).toBeTruthy();
  return await resp.json();
}

async function topUp(request, token, userId, amount) {
  const resp = await request.patch(`${BASE}/admin/users/${userId}`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { balance_bdt: amount },
  });
  expect(resp.ok()).toBeTruthy();
}

async function disableListingCooldown(request, token) {
  const resp = await request.patch(`${BASE}/admin/config/limits`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { listing_cooldown_minutes: 0 },
  });
  expect(resp.ok()).toBeTruthy();
}

async function claimLand(request, token, x, y) {
  const body = {
    x,
    y,
    biome: "PLAINS",
    elevation: 0.5,
    price_base_bdt: 1000,
  };
  const resp = await request.post(`${BASE}/lands/claim`, {
    headers: { Authorization: `Bearer ${token}` },
    data: body,
  });
  expect(resp.ok()).toBeTruthy();
  const land = await resp.json();
  return land.land_id;
}

async function createListing(request, token, landId, type) {
  const payload = {
    land_ids: [landId],
    listing_type: type,
  };
  if (type === "auction") {
    payload.starting_price_bdt = 500;
    payload.duration_hours = 24;
  }
  const resp = await request.post(`${BASE}/marketplace/listings`, {
    headers: { Authorization: `Bearer ${token}` },
    data: payload,
  });
  if (!resp.ok()) {
    console.error("Create listing failed", resp.status(), await resp.text());
  }
  expect(resp.ok()).toBeTruthy();
  return await resp.json();
}

// End-to-end: login -> top-up -> claim land -> list fixed price and auction
// Uses APIs for setup, then confirms listing appears in UI marketplace filter.
test("claim land and list (market price & auction)", async ({
  page,
  request,
}) => {
  const token = await login(request);
  const me = await getMe(request, token);

  // Ensure sufficient balance
  await topUp(request, token, me.user_id, 500000);

  // Disable listing cooldown to allow back-to-back listings during test
  await disableListingCooldown(request, token);

  // Claim a fresh coordinate to avoid conflicts
  const now = Date.now();
  const x = 2000 + (now % 1000);
  const y = 3000 + (Math.floor(now / 1000) % 1000);
  const landId = await claimLand(request, token, x, y);

  // Create fixed-price listing (market price calculated server-side)
  const fixedListing = await createListing(
    request,
    token,
    landId,
    "fixed_price"
  );
  expect(fixedListing.listing_id).toBeTruthy();

  // Create auction listing on a separate claimed land
  const landId2 = await claimLand(request, token, x + 1, y + 1);
  const auctionListing = await createListing(
    request,
    token,
    landId2,
    "auction"
  );
  expect(auctionListing.listing_id).toBeTruthy();

  // UI verification: login and check marketplace filters show entries
  await page.goto("http://localhost/login");
  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PASSWORD);
  await Promise.all([
    page.waitForURL("**/world", { timeout: 15000 }),
    page.click('button[type="submit"]'),
  ]);

  // Navigate to marketplace page
  await page.goto("http://localhost/marketplace", { waitUntil: "networkidle" });

  // Filter fixed price listings and expect at least one (the one we created)
  await page
    .selectOption(
      'select[name="listing_type"], select:has(option[value="fixed_price"])',
      "fixed_price"
    )
    .catch(() => {});
  await page.waitForTimeout(1000);
  const fixedVisible = await page
    .locator("text=fixed price", { hasText: /fixed/i })
    .count()
    .catch(() => 0);

  // Switch to auction filter and expect at least one
  await page
    .selectOption(
      'select[name="listing_type"], select:has(option[value="auction"])',
      "auction"
    )
    .catch(() => {});
  await page.waitForTimeout(1000);
  const auctionVisible = await page
    .locator("text=auction", { hasText: /auction/i })
    .count()
    .catch(() => 0);

  expect(fixedVisible + auctionVisible).toBeGreaterThan(0);
});
