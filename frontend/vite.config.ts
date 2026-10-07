import { defineConfig } from "vite";

// Two entries built into the Python package's static folder: stage.ts, tiny, loads the three.js world
// (a separate chunk) only when the stage scrolls into view, and ui.ts, the small script behind the
// interface (theme, shortcuts, predictions).
export default defineConfig({
  base: "/static/dist/",
  build: {
    outDir: "../src/orgestra/static/dist",
    emptyOutDir: true,
    // three.js is most of the lazy world chunk; it loads only when the stage is on screen.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      input: { stage: "src/stage.ts", ui: "src/ui.ts" },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
      },
    },
  },
});
