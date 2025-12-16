const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 75 });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
  });

  const logs = [];
  const cameraHistory = [];

  page.on("console", (msg) => {
    const text = msg.text();
    logs.push(text);
    // Capture camera coords from lines like: "📐 Viewport: 1280x720, Zoom: 1.00, Camera: (-36, -27)"
    const m = text.match(
      /Camera:\s*\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)/
    );
    if (m) {
      const x = parseFloat(m[1]);
      const y = parseFloat(m[2]);
      cameraHistory.push({ x, y, text, ts: Date.now() });
    }
    console.log("[PAGE]", text);
  });

  try {
    console.log("Open login and sign in");
    await page.goto("http://localhost/login", { waitUntil: "networkidle" });

    const emailSelector = 'input[type="email"], input[name="email"]';
    const passSelector = 'input[type="password"], input[name="password"]';
    const loginButtonSelector = 'button[type="submit"]';

    if (await page.$(emailSelector)) {
      const creds = require("../login_demo.json");
      await page.fill(emailSelector, creds.email);
      await page.fill(passSelector, creds.password);
      await Promise.all([
        page.click(loginButtonSelector),
        page
          .waitForNavigation({ waitUntil: "networkidle", timeout: 15000 })
          .catch(() => {}),
      ]);
    }

    console.log("Go to /world");
    await page.goto("http://localhost/world", { waitUntil: "networkidle" });
    await page.waitForSelector("canvas", { timeout: 60000 });

    const canvas = await page.$("canvas");
    const box = await canvas.boundingBox();
    const cx = box.x + box.width / 2;
    const cy = box.y + box.height / 2;

    // Wait a moment for camera logs to stabilize
    await page.waitForTimeout(1000);
    const initialCamera = cameraHistory.length
      ? cameraHistory[cameraHistory.length - 1]
      : null;
    console.log("Initial camera:", initialCamera);

    // Small mouse move WITHOUT pressing - should NOT pan the camera
    await page.mouse.move(cx + 5, cy + 5);
    await page.waitForTimeout(600);

    const afterMoveCamera = cameraHistory.length
      ? cameraHistory[cameraHistory.length - 1]
      : null;
    console.log("Camera after small hover move:", afterMoveCamera);

    // Analyze whether camera changed without mouse down
    const movedWhileNotDown =
      initialCamera &&
      afterMoveCamera &&
      (initialCamera.x !== afterMoveCamera.x ||
        initialCamera.y !== afterMoveCamera.y);
    console.log("Pan occurred without pressing?", movedWhileNotDown);

    // Now perform click+drag to pan
    await page.mouse.move(cx, cy);
    await page.mouse.down({ button: "left" });
    await page.mouse.move(cx + 120, cy + 50, { steps: 12 });
    await page.waitForTimeout(300);
    await page.mouse.up();

    const afterDragCamera = cameraHistory.length
      ? cameraHistory[cameraHistory.length - 1]
      : null;
    console.log("Camera after drag:", afterDragCamera);

    // Ctrl+Click to multi-select (use page.click with modifiers so originalEvent.ctrlKey is set)
    const canvasBox = await canvas.boundingBox();
    const relX = canvasBox.width / 2 + 60;
    const relY = canvasBox.height / 2;
    await page.click("canvas", {
      position: { x: relX, y: relY },
      modifiers: ["Control"],
    });
    await page.waitForTimeout(500);

    // Summarize logs for selection events
    const selectionLogs = logs.filter((l) =>
      /Selected land|toggleLandSelection|multi-select|multiSelect/.test(l)
    );

    console.log("\n--- Summary ---");
    console.log("initialCamera:", initialCamera);
    console.log("afterMoveCamera:", afterMoveCamera);
    console.log("movedWhileNotDown:", movedWhileNotDown);
    console.log("afterDragCamera:", afterDragCamera);
    console.log("selection-related logs:", selectionLogs.slice(-20));

    console.log("\nLeave browser open for 30s for manual inspection");
    await page.waitForTimeout(30000);
  } catch (err) {
    console.error("Headful test error:", err);
  } finally {
    await browser.close();
  }
})();
