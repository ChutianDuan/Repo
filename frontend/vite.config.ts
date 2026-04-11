import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_PROXY_TARGET || "http://127.0.0.1:8080";

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 5173,
      proxy: {
        "/health": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/v1": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
