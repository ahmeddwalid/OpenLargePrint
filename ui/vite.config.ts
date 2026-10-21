import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";

const here = dirname(fileURLToPath(import.meta.url));

// The reading fonts live with the engine, which embeds them in every export. The
// interface shows the same files (font previews, the in-app reader), copied in
// at build time so the repository holds one copy.
function readingFonts(): Plugin {
  const source = resolve(here, "../src/openlargeprint/exporters/fonts");
  const target = resolve(here, "public/fonts/reading");
  const sync = () => {
    if (!existsSync(source)) return;
    mkdirSync(target, { recursive: true });
    for (const name of readdirSync(source)) {
      if (!/\.(ttf|txt)$/.test(name) || name.startsWith("DejaVu")) continue;
      const from = join(source, name);
      const to = join(target, name);
      if (!existsSync(to) || statSync(to).mtimeMs < statSync(from).mtimeMs) copyFileSync(from, to);
    }
  };
  return { name: "reading-fonts", buildStart: sync, configureServer: sync };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), readingFonts()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
  build: {
    target: "esnext",
    minify: true,
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/__tests__/setup.ts"],
    globals: true,
  },
});
