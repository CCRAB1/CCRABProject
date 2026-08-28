import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  build: {
    outDir: resolve(__dirname, "static/build"),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, "frontend/platform_frontend.js"),
      output: {
        entryFileNames: "platform_frontend.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});