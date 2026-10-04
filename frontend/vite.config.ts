import { defineConfig } from "vite";

// One entry, stage.ts, built into the Python package's static folder. It is tiny and loads the
// three.js world (a separate chunk) only when the stage scrolls into view.
export default defineConfig({
  base: "/static/dist/",
  build: {
    outDir: "../src/orgestra/static/dist",
    emptyOutDir: true,
    // three.js is most of the lazy world chunk; it loads only when the stage is on screen.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      input: "src/stage.ts",
      output: {
        entryFileNames: "stage.js",
        chunkFileNames: "chunks/[name]-[hash].js",
      },
    },
  },
});
