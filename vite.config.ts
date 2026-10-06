import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const ports = JSON.parse(
  readFileSync(resolve(__dirname, "config/ports.json"), "utf-8"),
);

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  clearScreen: false,
  esbuild: {
    // 发行构建去掉 console/debugger，降低逆向可读性
    drop: mode === "production" ? ["console", "debugger"] : [],
    legalComments: "none",
  },
  build: {
    sourcemap: false,
    minify: "esbuild",
    cssMinify: true,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // 打散入口命名，避免一眼看到业务模块结构
        entryFileNames: "assets/[hash].js",
        chunkFileNames: "assets/[hash].js",
        assetFileNames: "assets/[hash][extname]",
      },
    },
  },
  server: {
    port: ports.frontend.port,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: ports.frontend.hmrPort,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
}));
