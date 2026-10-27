#!/usr/bin/env node
// JSON stdin bridge for Python skills; no second Python Playwright installation.
import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { launchChromium } from "./shared-playwright.mjs";

async function render(request) {
  if (!["slides", "card"].includes(request.action)) throw new Error("Unknown local render action");
  const browser = await launchChromium({ args: ["--allow-file-access-from-files"] });
  try {
    const context = await browser.newContext({
      viewport: { width: request.width, height: request.height }, deviceScaleFactor: request.scale ?? 1,
    });
    const page = await context.newPage();
    await page.goto(pathToFileURL(resolve(request.html)).href, { waitUntil: "domcontentloaded" });
    try { await page.waitForLoadState("load", { timeout: 8000 }); }
    catch (error) { if (error.name !== "TimeoutError") throw error; }
    if (request.action === "card") {
      await page.waitForFunction(() => document.querySelector("#card-check"), undefined, { timeout: 8000 });
      const check = await page.locator("#card-check").textContent();
      // Let the caller validate overflow before it requests a screenshot.
      if (request.output) await page.screenshot({ path: request.output });
      return { check: JSON.parse(check) };
    }
    const selectors = ["section.slide", "section[class*='slide']", ".slide", "section"];
    let slides = page.locator(selectors[0]);
    for (const selector of selectors) {
      slides = page.locator(selector);
      if (await slides.count()) break;
    }
    await page.evaluate(() => {
      document.querySelectorAll("section.slide,.slide,[data-animate],.animate,.reveal,.fade-in").forEach(el => {
        el.classList.add("visible", "active", "shown");
      });
    });
    await page.waitForTimeout(700);
    const files = [];
    for (let i = 0; i < await slides.count(); i++) {
      const file = join(request.output, `slide_${String(i + 1).padStart(2, "0")}.png`);
      writeFileSync(file, await slides.nth(i).screenshot({ type: "png" }));
      files.push(file);
    }
    return { files };
  } finally { await browser.close(); }
}
try { console.log(JSON.stringify(await render(JSON.parse(readFileSync(0, "utf8"))))); }
catch (error) { console.error(error.message); process.exitCode = 1; }
