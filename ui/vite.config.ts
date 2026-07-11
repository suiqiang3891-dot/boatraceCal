import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.indexOf("/node_modules/echarts/") !== -1) {
            return "echarts";
          }
          if (id.indexOf("/node_modules/") !== -1) {
            return "vendor";
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: false,
  },
});
