/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// The API runs on :8001 (or VITE_API_PROXY). In dev, Vite proxies API paths so the browser only talks to one origin.
const API = process.env.VITE_API_PROXY || "http://localhost:8001";
const apiPaths = ["/auth", "/catalog", "/booking", "/intake", "/pipeline", "/triage", "/queue", "/doctor", "/ehr", "/me", "/health", "/config", "/abdm"];

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "LifeLine (demo)",
        short_name: "LifeLine",
        description: "Course-project prototype with synthetic data. Not a medical device.",
        theme_color: "#0b5c4a",
        background_color: "#ffffff",
        display: "standalone",
        start_url: "/",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
      },
      workbox: {
        // App shell only. API responses (patient data) are never cached by the service worker.
        navigateFallbackDenylist: apiPaths.map((p) => new RegExp("^" + p)),
        runtimeCaching: [],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: Object.fromEntries(apiPaths.map((p) => [p, { target: API, changeOrigin: false }])),
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
