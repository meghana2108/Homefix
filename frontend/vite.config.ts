/// <reference types="vitest" />
import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// HTTPS_CERT / HTTPS_KEY are set by scripts/https_dev.sh so a phone on the same network can use the app
// (camera, mic and "Add to Home Screen" need https). The phone then calls /api on this same address,
// and the proxy below forwards it to the API, which only listens on 127.0.0.1.
const cert = process.env.HTTPS_CERT;
const key = process.env.HTTPS_KEY;
const https = cert && key ? { cert: readFileSync(cert), key: readFileSync(key) } : undefined;
const proxy = { "/api": { target: "http://127.0.0.1:8000", ws: true, changeOrigin: true } };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, https, proxy, host: https ? true : undefined },
  preview: { port: 5173, https, proxy, host: https ? true : undefined },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
