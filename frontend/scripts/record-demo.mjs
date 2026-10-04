// Record a short video of the app, for showing a frontend change in a pull request.
//
//   uv run orgestra                        # in another shell
//   npm run demo -- --out ../demo.webm      # from frontend/
//
// Options: --base <url> (default http://127.0.0.1:8000), --out <file.webm|file.mp4>,
// --query <text> (default "llm agnts"). An .mp4 output needs ffmpeg on PATH.
// Chromium: CHROMIUM_PATH, else the browser Playwright manages.
import { execFileSync } from "node:child_process";
import { mkdtempSync, renameSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { chromium } from "playwright-core";

const { values } = parseArgs({
  options: {
    base: { type: "string", default: "http://127.0.0.1:8000" },
    out: { type: "string", default: "demo.webm" },
    query: { type: "string", default: "llm agnts" },
  },
});
const size = { width: 1280, height: 800 };
const pause = (page, ms) => page.waitForTimeout(ms);
const started = Date.now();
const log = (step) => console.log(`${((Date.now() - started) / 1000).toFixed(1)}s ${step}`);

/** The tour: home with the characters talking, a search, People also ask, a talk and a speaker. */
async function tour(page) {
  await page.goto(values.base);
  log("home");
  await pause(page, 4000);
  await page.locator("#q").pressSequentially(values.query, { delay: 90 });
  await page.keyboard.press("Enter");
  await page.waitForSelector("#results");
  log("results");
  await pause(page, 3000);
  const question = page.locator(".people-ask summary").first();
  if (await question.count()) {
    await question.click();
    log("people also ask");
    await pause(page, 2500);
  }
  const hit = page.locator(".hit:not(.hit-pending) h3 a").first();
  await hit.click();
  await page.waitForSelector(".talk");
  log("talk");
  await pause(page, 3000);
  const speaker = page.locator(".talk .persona-chip").first();
  if (await speaker.count()) {
    await speaker.click();
    await page.waitForSelector(".persona");
    log("speaker");
    await pause(page, 3000);
  }
  await page.goBack();
  log("back");
  await pause(page, 2000);
}

const videoDir = mkdtempSync(join(tmpdir(), "orgestra-demo-"));
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  // Software WebGL, so the three.js stage renders in headless and CI browsers too.
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const context = await browser.newContext({ viewport: size, recordVideo: { dir: videoDir, size } });
const page = await context.newPage();
try {
  await tour(page);
} finally {
  await context.close(); // writes the video
  await browser.close();
}

const recorded = await page.video().path();
const out = resolve(values.out);
if (out.endsWith(".mp4")) {
  execFileSync("ffmpeg", [
    "-y",
    "-loglevel",
    "error",
    "-i",
    recorded,
    "-movflags",
    "+faststart",
    "-pix_fmt",
    "yuv420p",
    out,
  ]);
} else {
  renameSync(recorded, out);
}
rmSync(videoDir, { recursive: true, force: true });
console.log(`Recorded ${out}`);
