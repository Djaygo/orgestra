// Copy htmx and its SSE extension into the Python package, so the pages work without a Node build.
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
