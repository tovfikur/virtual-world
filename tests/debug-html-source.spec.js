import { test } from "@playwright/test";

test("Debug: Check page source for LivePanel", async ({ browser }) => {
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

  const pageHTML = await page.content();

  console.log("=== CHECKING PAGE HTML ===");
  console.log(`Page length: ${pageHTML.length}`);
  console.log(`Contains LivePanel: ${pageHTML.includes("LivePanel")}`);
  console.log(`Contains "Go Live": ${pageHTML.includes("Go Live")}`);
  console.log(`Contains "[live]": ${pageHTML.includes("[live]")}`);

  // Look for the Go Live button in HTML
  const goLiveIndex = pageHTML.indexOf("Go Live (Audio)");
  if (goLiveIndex > -1) {
    const snippet = pageHTML.substring(
      Math.max(0, goLiveIndex - 300),
      Math.min(pageHTML.length, goLiveIndex + 100)
    );
    console.log('\n=== HTML SNIPPET AROUND "Go Live (Audio)" ===');
    console.log(snippet);
  }

  //  Count how many React app divs
  const appDivCount = (pageHTML.match(/<div id="app"/g) || []).length;
  console.log(`\n⚠️ div#app count: ${appDivCount}`);
});
