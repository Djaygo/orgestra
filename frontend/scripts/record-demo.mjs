// Record a short video of the app, for showing a frontend change in a pull request.
//
//   uv run orgestra                        # in another shell
//   npm run demo -- --out ../demo.webm      # from frontend/
//
// Options: --base <url> (default http://127.0.0.1:8000), --out <file.webm|file.mp4>,
// --query <text> (default "agents"; "automation" for the slides tour), --tour full|slides|plaza
// (default full; slides and plaza are zoomed close-ups, of the match badges and of the plaza, and need an .mp4 output). An .mp4 output needs
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
const query = values.query ?? (values.tour === "slides" ? SLIDES_QUERY : "agents");
const size = { width: 1280, height: 800 };
const pause = (page, ms) => page.waitForTimeout(ms);
const started = Date.now();
const log = (step) => console.log(`${((Date.now() - started) / 1000).toFixed(1)}s ${step}`);

/** Smooth scroll to a vertical position, then wait for it to settle. */
async function scrollTo(page, top, ms = 1200) {
  await page.evaluate((y) => window.scrollTo({ top: y, behavior: "smooth" }), top);
  await pause(page, ms);
}

/** Search: "/" focuses the box, predictions open while typing, then the results with their filters. */
async function search(page) {
  await page.goto(values.base);
  log("home");
  await pause(page, 3000);
  await page.keyboard.press("/");
  await page.locator("#q").pressSequentially(query.slice(0, 4), { delay: 140 });
  await page.waitForSelector("#suggestions:not([hidden]) li");
  log("predictions");
  await pause(page, 1800);
  await page.keyboard.press("ArrowDown");
  await pause(page, 600);
  await page.keyboard.press("ArrowDown");
  await pause(page, 1000);
  await page.locator("#q").pressSequentially(query.slice(4), { delay: 110 });
  await page.keyboard.press("Enter");
  await page.waitForSelector("#results .talk-card");
  log("results");
  await pause(page, 2500);
  await page.locator(".filters a.chip", { hasText: "Slides" }).click();
  await page.waitForSelector(".filters a.chip[aria-current='true']");
  log("filtered to talks with slides");
  await pause(page, 2500);
  const question = page.locator(".people-ask summary").first();
  if (await question.count()) {
    await question.click();
    log("people also ask");
    await pause(page, 2000);
  }
}

/** The talk: the player, the abstract, related talks and the discussion with an edit and its history. */
async function talk(page) {
  await page.locator(".talk-card:not(.talk-card-pending) h3 a").first().click();
  await page.waitForSelector(".talk");
  log("talk");
  await pause(page, 2500);
  await scrollTo(page, 420, 2500);
  const discussion = await page
    .locator("#discussion")
    .evaluate((el) => el.getBoundingClientRect().top + window.scrollY);
  await scrollTo(page, discussion - 80, 1500);
  await page.locator("#new-body").click();
  await page.locator("#new-body").pressSequentially("How does this hold up at scale?", { delay: 50 });
  await page.locator(".segmented label", { hasText: "Question" }).click();
  await page.locator("#new-name").fill("Ada");
  await page.locator(".new-post button[type=submit]").click();
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
  await pause(page, 3000);
}

/** The theme toggle: switch to dark and back, in place. */
async function theme(page) {
  const toggle = page.locator("[data-theme-toggle]");
  if (!(await toggle.count())) {
    return;
  }
  await scrollTo(page, 0, 800);
  await toggle.click();
  await toggle.click();
  log("dark theme");
  await pause(page, 2500);
  await toggle.click();
  await pause(page, 600);
}

/** Browse: every talk of a year behind tabs, narrowed by the filter box as you type. */
async function browse(page) {
  await page.locator(".action[href='/browse']").first().click();
  await page.waitForSelector(".browse-list");
  log("browse");
  await pause(page, 1800);
  await page.locator("#browse-filter").pressSequentially("java", { delay: 140 });
  log("filtered");
  await pause(page, 2200);
  await page.locator(".filters a.chip", { hasText: "Speakers" }).click();
  await page.waitForSelector(".browse-list");
  await pause(page, 1800);
}

/** A speaker page, reached from the talk. */
async function speaker(page) {
  await page.locator(".browse-link").first().click();
  await page.waitForSelector(".speaker");
  log("speaker");
  await pause(page, 3000);
}

/** Report a bug: open the form from the top bar and fill it in, without sending anything. */
async function reportBug(page) {
  const button = page.locator(".report-button");
  if (!(await button.count())) {
    return;
  }
  await button.click();
  await page.waitForSelector("form.report-form");
  await page.locator("#report-title").pressSequentially("The search box loses my query", { delay: 50 });
  await page
    .locator("#report-description")
    .pressSequentially("I typed a long query, switched tabs and it was gone.", { delay: 40 });
  log("report form filled in");
  await pause(page, 2500);
}

/** A page that does not exist: the branded 404 with ways forward. */
async function notFound(page) {
  await page.goto(`${values.base}/talks/2025/nope`);
  await page.waitForSelector(".error-page");
  log("not found");
  await pause(page, 2500);
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
  const slideOnly = page
    .locator(".talk-card:has(.match-slides):not(:has(.match:not(.match-slides)))")
    .first();
  if (await slideOnly.count()) {
    const badge = slideOnly.locator(".match-slides");
    await badge.evaluate((el) => el.scrollIntoView({ block: "center" }));
    await badge.hover();
    log("a talk found only by its slides");
    await pause(page, 3000);
  }
}

/** The plaza close-up: a small cast on the home page, then speakers of the results and of a talk stepping
 * to the front row, with a hover card and a click through to their talk. */
async function plazaTour(page) {
  await page.goto(values.base);
  await pause(page, 7000);
  log("the cast on duty");
  const ambient = page.locator(".stage-tag:visible").nth(3);
  await ambient.hover({ force: true });
  log("one of them waves");
  await pause(page, 3000);
  await page.mouse.move(640, 100);
  await page.locator("#q").fill(SLIDES_QUERY);
  await page.keyboard.press("Enter");
  await page.waitForSelector("#results .talk-card");
  await pause(page, 1500);
  await scrollTo(page, 100000, 1500);
  log("the speakers of the results walk to the front");
  await pause(page, 9000);
  const front = page.locator(".stage-tag.front").nth(2);
  await front.locator(".stage-name").hover({ force: true });
  log("hover shows the talk");
  await pause(page, 3500);
  await front.locator(".stage-name").click({ force: true });
  await page.waitForSelector(".talk-head");
  await pause(page, 1500);
  await scrollTo(page, 100000, 1500);
  log("a talk brings its speakers and related ones");
  await pause(page, 9000);
  await page.locator(".stage-tag.front").first().focus();
  log("keyboard focus");
  await pause(page, 3000);
}

/** The tour: search with predictions and filters, a talk with its player and discussion, the theme,
 * Browse, a speaker, the report form and the 404. */
async function tour(page) {
  await search(page);
  await talk(page);
  await theme(page);
  await browse(page);
  await speaker(page);
  await reportBug(page);
  await notFound(page);
}

const videoDir = mkdtempSync(join(tmpdir(), "orgestra-demo-"));
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  // Software WebGL, so the three.js stage renders in headless and CI browsers too.
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
// The close-up records a small layout viewport (the compact layout) that ffmpeg scales up to `size`.
const zoomed = values.tour === "slides" || values.tour === "plaza";
const viewport = values.tour === "plaza" ? { width: 1024, height: 640 } : zoomed ? { width: 800, height: 500 } : size;
const context = await browser.newContext({ viewport, recordVideo: { dir: videoDir, size: viewport } });
const page = await context.newPage();
try {
  await ({ slides: slidesTour, plaza: plazaTour }[values.tour] ?? tour)(page);
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
