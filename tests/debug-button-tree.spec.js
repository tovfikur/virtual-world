import { test } from "@playwright/test";

test("Debug: Inspect button DOM tree", async ({ browser }) => {
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  const page = await context.newPage();

  // Navigate and login
  await page.goto("http://localhost", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  await page.fill('input[type="email"]', "topubiswas1234@gmail.com");
  await page.fill('input[type="password"]', "topubiswas1234@gmail.com");
  await page.click('button:has-text("Sign in")');
  await page.waitForURL("**/world", { timeout: 30000 });

  // Wait for world to load
  await page.waitForTimeout(5000);

  // Click on a land tile
  const canvas = page.locator("canvas").first();
  const canvasBox = await canvas.boundingBox();
  if (canvasBox) {
    await page.click("canvas", {
      position: { x: canvasBox.width / 2, y: canvasBox.height / 2 },
    });
    await page.waitForTimeout(2000);
  }

  // Get the button's parent HTML
  const html = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll("button"));
    const btn = buttons.find((b) => b.textContent.includes("Go Live (Audio)"));
    if (!btn) return "BUTTON NOT FOUND";

    // Get up to 3 parents
    let elem = btn;
    let html = "";
    for (let i = 0; i < 5 && elem; i++) {
      const tag = elem.tagName.toLowerCase();
      const classStr = elem.className ? `class="${elem.className}"` : "";
      html += `\n${"  ".repeat(i)}<${tag} ${classStr}>`;
      if (i === 0) html += "✓ BUTTON FOUND";
      elem = elem.parentElement;
    }
    return html;
  });

  console.log("=== BUTTON DOM TREE ===");
  console.log(html);

  // Also check the actual rendered HTML around the button
  const buttonHTML = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll("button"));
    const btn = buttons.find((b) => b.textContent.includes("Go Live (Audio)"));
    if (!btn) return "BUTTON NOT FOUND";
    return btn.outerHTML.substring(0, 300);
  });

  console.log("\n=== BUTTON HTML ===");
  console.log(buttonHTML);

  // Check if there's a React component attribute
  const reactKey = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll("button"));
    const btn = buttons.find((b) => b.textContent.includes("Go Live (Audio)"));
    if (!btn) return null;
    return Object.keys(btn).filter((k) => k.startsWith("__react")).length;
  });

  console.log(`\nReact attributes on button: ${reactKey}`);
});
