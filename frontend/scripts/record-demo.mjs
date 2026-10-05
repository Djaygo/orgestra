// Record a short video of the app, for showing a frontend change in a pull request.
//
//   uv run orgestra                        # in another shell
//   npm run demo -- --out ../demo.webm      # from frontend/
//
// Options: --base <url> (default http://127.0.0.1:8000), --out <file.webm|file.mp4>,
// --query <text> (default "llm agnts"; "automation" for the slides tour), --tour full|slides (default
// full; slides is a zoomed close-up of the match badges and needs an .mp4 output). An .mp4 output needs
// ffmpeg on PATH.
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
    query: { type: "string" },
    tour: { type: "string", default: "full" },
  },
});
// Words that decks of GOTO Copenhagen cover on slides, so the results mix title, abstract and slide badges.
const SLIDES_QUERY = "automation";
const query = values.query ?? (values.tour === "slides" ? SLIDES_QUERY : "llm agnts");
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
  await form
    .locator("textarea[name=body]")
    .pressSequentially("How does this hold up at scale?", { delay: 50 });
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

/** Report a bug: open the form from the top bar and fill it in, without sending anything. */
async function reportBug(page) {
  const button = page.locator(".report-button");
  if (!(await button.count())) {
    return;
  }
  await button.click();
  await page.waitForSelector("form.report-form");
  const form = page.locator("form.report-form");
  await form.locator("input[name=title]").pressSequentially("The search box loses my query", { delay: 50 });
  await form
    .locator("textarea[name=description]")
    .pressSequentially("I typed a long query, switched tabs and it was gone.", { delay: 40 });
  log("report form filled in");
  await pause(page, 2500);
  await page.goBack();
}

/** A close-up of the match badges: why each result matched and the slide the match is on. */
async function slidesTour(page) {
  await page.goto(values.base);
  log("home");
  await pause(page, 1500);
  await page.locator("#q").pressSequentially(query, { delay: 110 });
  await page.keyboard.press("Enter");
  await page.waitForSelector(".hit-matches");
  log("results with badges");
  await pause(page, 3000);
  for (const badge of (await page.locator(".hit-matches").first().locator(".match").all()).slice(0, 4)) {
    await badge.hover();
    await pause(page, 1200);
  }
  const slide = page.locator(".match-slides").first();
  await slide.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await slide.hover();
  log("slide badge");
  await pause(page, 3000);
  const slideOnly = page.locator(".hit:has(.match-slides):not(:has(.match:not(.match-slides)))").first();
  if (await slideOnly.count()) {
    const badge = slideOnly.locator(".match-slides");
    await badge.evaluate((el) => el.scrollIntoView({ block: "center" }));
    await badge.hover();
    log("a talk found only by its slides");
    await pause(page, 3000);
  }
}

/** The tour: home with the characters talking, a search, People also ask, a talk and a speaker. */
async function tour(page) {
  await page.goto(values.base);
  log("home");
  await pause(page, 4000);
  await page.locator("#q").pressSequentially(query, { delay: 90 });
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
  await reportBug(page);
}

const videoDir = mkdtempSync(join(tmpdir(), "orgestra-demo-"));
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  // Software WebGL, so the three.js stage renders in headless and CI browsers too.
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
// The close-up records a small layout viewport (the compact layout) that ffmpeg scales up to `size`.
const zoomed = values.tour === "slides";
const viewport = zoomed ? { width: 800, height: 500 } : size;
const context = await browser.newContext({ viewport, recordVideo: { dir: videoDir, size: viewport } });
const page = await context.newPage();
try {
  await (values.tour === "slides" ? slidesTour(page) : tour(page));
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
    "-vf",
    `scale=${size.width}:${size.height}:flags=lanczos`,
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
