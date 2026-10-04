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

/** Discussion: ask a question, reply, correct the question and open its history. */
async function discuss(page) {
  const form = page.locator("form.new-post");
  await form.scrollIntoViewIfNeeded();
  await form.locator("select[name=kind]").selectOption("question");
  await form.locator("input[name=name]").fill("Ada");
  await form.locator("textarea[name=body]").pressSequentially("How does this hold up at scale?", { delay: 50 });
  await form.locator("button[type=submit]").click();
  await page.waitForSelector(".post");
  log("question posted");
  await pause(page, 1500);
  const post = page.locator(".post").first();
  await post.locator("details.reply > summary").click();
  await post.locator("details.reply input[name=name]").fill("Grace");
  await post.locator("details.reply textarea").pressSequentially("Mostly by sharding early.", { delay: 50 });
  await post.locator("details.reply button[type=submit]").click();
  await page.waitForSelector(".post .post");
  log("reply posted");
  await pause(page, 1500);
  await post.locator("details.edit > summary").first().click();
  await post.locator("details.edit textarea").first().fill("How does this hold up at 10k users?");
  await post.locator("details.edit button[type=submit]").first().click();
  await page.waitForSelector("details.history");
  log("edited");
  await pause(page, 1000);
  await page.locator("details.history > summary").first().click();
  log("history");
  await pause(page, 3500);
}

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
  await discuss(page);
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
