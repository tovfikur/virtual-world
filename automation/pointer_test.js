const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  page.on("console", (msg) => console.log("[BROWSER]", msg.text()));

  try {
    console.log("Navigating to http://localhost/login to sign in");
    await page.goto("http://localhost/login", { waitUntil: "networkidle" });

    // Fill login form if present
    const emailSelector = 'input[type="email"], input[name="email"]';
    const passSelector = 'input[type="password"], input[name="password"]';
    const loginButtonSelector = 'button[type="submit"]';

    if (await page.$(emailSelector)) {
      console.log("Login form detected — signing in");
      const creds = require("../login_demo.json");
      await page.fill(emailSelector, creds.email);
      await page.fill(passSelector, creds.password);
      await Promise.all([
        page.click(loginButtonSelector),
        page
          .waitForNavigation({ waitUntil: "networkidle", timeout: 15000 })
          .catch(() => {}),
      ]);
    } else {
      console.log("No login form detected — continuing");
    }

    console.log("Navigating to /world");
    await page.goto("http://localhost/world", { waitUntil: "networkidle" });
    await page.waitForSelector("canvas", { timeout: 60000 });
    const canvas = await page.$("canvas");
    const box = await canvas.boundingBox();

    const initialCursor = await page.evaluate((c) => {
      return window.getComputedStyle(c).cursor || "";
    }, canvas);
    console.log("Initial canvas cursor:", initialCursor);

    // Move mouse over canvas center without pressing
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForTimeout(300);
    const afterMoveCursor = await page.evaluate(
      (c) => window.getComputedStyle(c).cursor || "",
      canvas
    );
    console.log("Cursor after hover/move:", afterMoveCursor);

    // Perform click (tap) without dragging
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForTimeout(500);

    // Now simulate click+drag (left button) to pan
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down({ button: "left" });
    await page.waitForTimeout(100);
    await page.mouse.move(
      box.x + box.width / 2 + 100,
      box.y + box.height / 2 + 40,
      { steps: 8 }
    );
    await page.waitForTimeout(200);
    const duringDragCursor = await page.evaluate(
      (c) => window.getComputedStyle(c).cursor || "",
      canvas
    );
    console.log("Cursor during/after drag:", duringDragCursor);
    await page.mouse.up();

    // Ctrl+click to multi-select (desktop)
    await page.keyboard.down("Control");
    await page.mouse.click(box.x + box.width / 2 + 60, box.y + box.height / 2);
    await page.keyboard.up("Control");
    await page.waitForTimeout(500);

    console.log("Test actions complete.");
  } catch (err) {
    console.error("Test error:", err);
    try {
      const html = await page.content();
      console.error(
        "Current page HTML snapshot (first 2000 chars):\n",
        html.substring(0, 2000)
      );
    } catch (e) {
      // ignore
    }
  } finally {
    await browser.close();
    console.log("Browser closed.");
  }
})();
