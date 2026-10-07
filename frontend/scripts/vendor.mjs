// Copy htmx, its SSE extension and the Roboto font into the Python package, so the pages work without a Node build.
// Run after bumping either package: `npm run vendor`.
import { copyFileSync, mkdirSync } from "node:fs";

const target = new URL("../../src/orgestra/static/vendor/", import.meta.url);
mkdirSync(target, { recursive: true });
copyFileSync(
  new URL("../node_modules/htmx.org/dist/htmx.min.js", import.meta.url),
  new URL("htmx.min.js", target),
);
copyFileSync(
  new URL("../node_modules/htmx-ext-sse/dist/sse.min.js", import.meta.url),
  new URL("sse.js", target),
);

const fonts = new URL("../../src/orgestra/static/fonts/", import.meta.url);
mkdirSync(fonts, { recursive: true });
const roboto = "../node_modules/@fontsource-variable/roboto/";
copyFileSync(
  new URL(`${roboto}files/roboto-latin-wght-normal.woff2`, import.meta.url),
  new URL("roboto-latin-wght-normal.woff2", fonts),
);
copyFileSync(new URL(`${roboto}LICENSE`, import.meta.url), new URL("roboto-LICENSE.txt", fonts));
