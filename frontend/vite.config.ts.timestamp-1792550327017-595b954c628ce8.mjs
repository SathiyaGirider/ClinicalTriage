// vite.config.ts
import { defineConfig } from "file:///D:/projects/ClinicalTriage/frontend/node_modules/vite/dist/node/index.js";
import react from "file:///D:/projects/ClinicalTriage/frontend/node_modules/@vitejs/plugin-react/dist/index.mjs";
import { VitePWA } from "file:///D:/projects/ClinicalTriage/frontend/node_modules/vite-plugin-pwa/dist/index.js";
var API = process.env.VITE_API_PROXY || "http://localhost:8000";
var apiPaths = ["/auth", "/catalog", "/booking", "/intake", "/pipeline", "/triage", "/queue", "/doctor", "/ehr", "/me", "/health", "/config"];
var vite_config_default = defineConfig({
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
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }]
      },
      workbox: {
        // App shell only. API responses (patient data) are never cached by the service worker.
        navigateFallbackDenylist: apiPaths.map((p) => new RegExp("^" + p)),
        runtimeCaching: []
      }
    })
  ],
  server: {
    port: 5173,
    proxy: Object.fromEntries(apiPaths.map((p) => [p, { target: API, changeOrigin: false }]))
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"]
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJEOlxcXFxwcm9qZWN0c1xcXFxDbGluaWNhbFRyaWFnZVxcXFxmcm9udGVuZFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiRDpcXFxccHJvamVjdHNcXFxcQ2xpbmljYWxUcmlhZ2VcXFxcZnJvbnRlbmRcXFxcdml0ZS5jb25maWcudHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL0Q6L3Byb2plY3RzL0NsaW5pY2FsVHJpYWdlL2Zyb250ZW5kL3ZpdGUuY29uZmlnLnRzXCI7Ly8vIDxyZWZlcmVuY2UgdHlwZXM9XCJ2aXRlc3RcIiAvPlxyXG5pbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tIFwidml0ZVwiO1xyXG5pbXBvcnQgcmVhY3QgZnJvbSBcIkB2aXRlanMvcGx1Z2luLXJlYWN0XCI7XHJcbmltcG9ydCB7IFZpdGVQV0EgfSBmcm9tIFwidml0ZS1wbHVnaW4tcHdhXCI7XHJcblxyXG4vLyBUaGUgQVBJIHJ1bnMgb24gOjgwMDAuIEluIGRldiwgVml0ZSBwcm94aWVzIEFQSSBwYXRocyBzbyB0aGUgYnJvd3NlciBvbmx5IHRhbGtzIHRvIG9uZSBvcmlnaW4uXHJcbmNvbnN0IEFQSSA9IHByb2Nlc3MuZW52LlZJVEVfQVBJX1BST1hZIHx8IFwiaHR0cDovL2xvY2FsaG9zdDo4MDAwXCI7XHJcbmNvbnN0IGFwaVBhdGhzID0gW1wiL2F1dGhcIiwgXCIvY2F0YWxvZ1wiLCBcIi9ib29raW5nXCIsIFwiL2ludGFrZVwiLCBcIi9waXBlbGluZVwiLCBcIi90cmlhZ2VcIiwgXCIvcXVldWVcIiwgXCIvZG9jdG9yXCIsIFwiL2VoclwiLCBcIi9tZVwiLCBcIi9oZWFsdGhcIiwgXCIvY29uZmlnXCJdO1xyXG5cclxuZXhwb3J0IGRlZmF1bHQgZGVmaW5lQ29uZmlnKHtcclxuICBwbHVnaW5zOiBbXHJcbiAgICByZWFjdCgpLFxyXG4gICAgVml0ZVBXQSh7XHJcbiAgICAgIHJlZ2lzdGVyVHlwZTogXCJhdXRvVXBkYXRlXCIsXHJcbiAgICAgIGluY2x1ZGVBc3NldHM6IFtcImljb24uc3ZnXCJdLFxyXG4gICAgICBtYW5pZmVzdDoge1xyXG4gICAgICAgIG5hbWU6IFwiTGlmZUxpbmUgKGRlbW8pXCIsXHJcbiAgICAgICAgc2hvcnRfbmFtZTogXCJMaWZlTGluZVwiLFxyXG4gICAgICAgIGRlc2NyaXB0aW9uOiBcIkNvdXJzZS1wcm9qZWN0IHByb3RvdHlwZSB3aXRoIHN5bnRoZXRpYyBkYXRhLiBOb3QgYSBtZWRpY2FsIGRldmljZS5cIixcclxuICAgICAgICB0aGVtZV9jb2xvcjogXCIjMGI1YzRhXCIsXHJcbiAgICAgICAgYmFja2dyb3VuZF9jb2xvcjogXCIjZmZmZmZmXCIsXHJcbiAgICAgICAgZGlzcGxheTogXCJzdGFuZGFsb25lXCIsXHJcbiAgICAgICAgc3RhcnRfdXJsOiBcIi9cIixcclxuICAgICAgICBpY29uczogW3sgc3JjOiBcImljb24uc3ZnXCIsIHNpemVzOiBcImFueVwiLCB0eXBlOiBcImltYWdlL3N2Zyt4bWxcIiwgcHVycG9zZTogXCJhbnlcIiB9XSxcclxuICAgICAgfSxcclxuICAgICAgd29ya2JveDoge1xyXG4gICAgICAgIC8vIEFwcCBzaGVsbCBvbmx5LiBBUEkgcmVzcG9uc2VzIChwYXRpZW50IGRhdGEpIGFyZSBuZXZlciBjYWNoZWQgYnkgdGhlIHNlcnZpY2Ugd29ya2VyLlxyXG4gICAgICAgIG5hdmlnYXRlRmFsbGJhY2tEZW55bGlzdDogYXBpUGF0aHMubWFwKChwKSA9PiBuZXcgUmVnRXhwKFwiXlwiICsgcCkpLFxyXG4gICAgICAgIHJ1bnRpbWVDYWNoaW5nOiBbXSxcclxuICAgICAgfSxcclxuICAgIH0pLFxyXG4gIF0sXHJcbiAgc2VydmVyOiB7XHJcbiAgICBwb3J0OiA1MTczLFxyXG4gICAgcHJveHk6IE9iamVjdC5mcm9tRW50cmllcyhhcGlQYXRocy5tYXAoKHApID0+IFtwLCB7IHRhcmdldDogQVBJLCBjaGFuZ2VPcmlnaW46IGZhbHNlIH1dKSksXHJcbiAgfSxcclxuICB0ZXN0OiB7XHJcbiAgICBlbnZpcm9ubWVudDogXCJqc2RvbVwiLFxyXG4gICAgZ2xvYmFsczogdHJ1ZSxcclxuICAgIHNldHVwRmlsZXM6IFtcIi4vc3JjL3Rlc3Qtc2V0dXAudHNcIl0sXHJcbiAgfSxcclxufSk7XHJcbiJdLAogICJtYXBwaW5ncyI6ICI7QUFDQSxTQUFTLG9CQUFvQjtBQUM3QixPQUFPLFdBQVc7QUFDbEIsU0FBUyxlQUFlO0FBR3hCLElBQU0sTUFBTSxRQUFRLElBQUksa0JBQWtCO0FBQzFDLElBQU0sV0FBVyxDQUFDLFNBQVMsWUFBWSxZQUFZLFdBQVcsYUFBYSxXQUFXLFVBQVUsV0FBVyxRQUFRLE9BQU8sV0FBVyxTQUFTO0FBRTlJLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzFCLFNBQVM7QUFBQSxJQUNQLE1BQU07QUFBQSxJQUNOLFFBQVE7QUFBQSxNQUNOLGNBQWM7QUFBQSxNQUNkLGVBQWUsQ0FBQyxVQUFVO0FBQUEsTUFDMUIsVUFBVTtBQUFBLFFBQ1IsTUFBTTtBQUFBLFFBQ04sWUFBWTtBQUFBLFFBQ1osYUFBYTtBQUFBLFFBQ2IsYUFBYTtBQUFBLFFBQ2Isa0JBQWtCO0FBQUEsUUFDbEIsU0FBUztBQUFBLFFBQ1QsV0FBVztBQUFBLFFBQ1gsT0FBTyxDQUFDLEVBQUUsS0FBSyxZQUFZLE9BQU8sT0FBTyxNQUFNLGlCQUFpQixTQUFTLE1BQU0sQ0FBQztBQUFBLE1BQ2xGO0FBQUEsTUFDQSxTQUFTO0FBQUE7QUFBQSxRQUVQLDBCQUEwQixTQUFTLElBQUksQ0FBQyxNQUFNLElBQUksT0FBTyxNQUFNLENBQUMsQ0FBQztBQUFBLFFBQ2pFLGdCQUFnQixDQUFDO0FBQUEsTUFDbkI7QUFBQSxJQUNGLENBQUM7QUFBQSxFQUNIO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixPQUFPLE9BQU8sWUFBWSxTQUFTLElBQUksQ0FBQyxNQUFNLENBQUMsR0FBRyxFQUFFLFFBQVEsS0FBSyxjQUFjLE1BQU0sQ0FBQyxDQUFDLENBQUM7QUFBQSxFQUMxRjtBQUFBLEVBQ0EsTUFBTTtBQUFBLElBQ0osYUFBYTtBQUFBLElBQ2IsU0FBUztBQUFBLElBQ1QsWUFBWSxDQUFDLHFCQUFxQjtBQUFBLEVBQ3BDO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
