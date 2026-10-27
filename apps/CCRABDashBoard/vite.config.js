import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  build: {
    outDir: resolve(__dirname, "static/build"),
    minify: false,
    target: "esnext",
    emptyOutDir: true,
    rollupOptions: {
      treeshake: false,
      input: resolve(__dirname, "frontend/platform_frontend.js"),
      output: {
        preserveModules: true,
        preserveModulesRoot: resolve(__dirname),
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
