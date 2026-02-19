import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import http from "node:http";

const ipv4Agent = new http.Agent({ family: 4 });

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        agent: ipv4Agent,
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes, _req, res) => {
            const ct = proxyRes.headers["content-type"] || "";
            if (ct.includes("text/event-stream")) {
              delete proxyRes.headers["content-encoding"];
              proxyRes.headers["Cache-Control"] = "no-cache";
              proxyRes.headers["X-Accel-Buffering"] = "no";
              if (
                "flushHeaders" in res &&
                typeof res.flushHeaders === "function"
              ) {
                res.flushHeaders();
              }
            }
          });
        },
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
