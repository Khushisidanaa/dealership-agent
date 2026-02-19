import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import http from "node:http";
// Force IPv4 for proxy so we don't hit ECONNREFUSED on ::1 when backend listens on 127.0.0.1
var ipv4Agent = new http.Agent({ family: 4 });
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/api": {
                target: "http://127.0.0.1:8000",
                changeOrigin: true,
                agent: ipv4Agent,
            },
        },
    },
    build: {
        outDir: "dist",
        sourcemap: false,
    },
});
