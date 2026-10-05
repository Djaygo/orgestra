// Screenshot every page of the app at phone and desktop size, in light and dark, for design review.
//
//   uv run orgestra                                           # in another shell
//   npm run capture -- --out ../shots/before                   # from frontend/
//
// Options: --base <url> (default http://127.0.0.1:8000), --out <dir>, --only <name,name> (page names).
// A question with a reply is posted on the video talk first so the discussion has something to show:
// run it against a throwaway database (ORGESTRA_DB_PATH). Chromium: CHROMIUM_PATH, else Playwright's.
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { chromium } from "playwright-core";

const { values } = parseArgs({
  options: {
    base: { type: "string", default: "http://127.0.0.1:8000" },
    out: { type: "string", default: "shots" },
    only: { type: "string" },
  },
});

const VIDEO_TALK = "/talks/2025/the-way-the-future-was";
const PAGES = [
  { name: "home", path: "/" },
  { name: "results", path: "/search?q=automation" },
  { name: "results-filtered", path: "/search?q=automation&year=2025&slides=1" },
  { name: "no-results", path: "/search?q=zzzxqj" },
  { name: "talk-video", path: VIDEO_TALK },
  { name: "talk-slides", path: "/talks/2025/how-fast-can-you-parse-a-file-with-1-billion-rows-of-weather-data-using-java" },
  { name: "talk-pending", path: "/talks/2025/residues-time-change-and-uncertainty-in-software-architecture" },
  { name: "speaker", path: "/speakers/kevlin-henney" },
  { name: "report", path: "/report?from=/" },
  { name: "not-found", path: "/talks/2025/nope" },
];
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800, scale: 1 },
  { name: "mobile", width: 390, height: 844, scale: 2 },
];
const SCHEMES = ["light", "dark"];
const only = values.only?.split(",");
const out = resolve(values.out);
mkdirSync(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});

async function seedDiscussion() {
  const context = await browser.newContext();
  const form = (data) => ({ form: data });
  const question = await context.request.post(`${values.base}${VIDEO_TALK}/posts`, {
    ...form({ kind: "question", name: "Ada", body: "How would you apply this to a team of ten?" }),
    maxRedirects: 0,
  });
  if (question.status() === 303) {
    await context.request.post(`${values.base}/posts/1/replies`, {
      ...form({ name: "Grace", body: "Start with one decision, write it down, and revisit it in a month." }),
      maxRedirects: 0,
    });
  }
  await context.close();
}

async function shoot(context, name, viewport, scheme, path, act) {
  const page = await context.newPage();
  await page.goto(`${values.base}${path}`);
  await page.waitForLoadState("load");
  await page.waitForTimeout(1200);
  if (act) {
    await act(page);
  }
  const file = join(out, `${name}-${viewport.name}-${scheme}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(file);
  await page.close();
}

await seedDiscussion();
for (const viewport of VIEWPORTS) {
  for (const scheme of SCHEMES) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: viewport.scale,
      colorScheme: scheme,
    });
    for (const { name, path } of PAGES) {
      if (!only || only.includes(name)) {
        await shoot(context, name, viewport, scheme, path);
      }
    }
    if (!only || only.includes("sources")) {
      await shoot(context, "sources", viewport, scheme, "/search?q=automation", async (page) => {
        await page.locator(".sources-button, [data-sources-toggle]").first().click();
        await page.waitForTimeout(500);
      });
    }
    await context.close();
  }
}
await browser.close();
