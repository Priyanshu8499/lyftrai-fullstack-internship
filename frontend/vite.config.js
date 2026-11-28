import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id))
            return "react-vendor";
          if (
            /react-markdown|remark-|rehype-|unified|micromark|mdast|hast|highlight\.js|lowlight/.test(
              id,
            )
          )
            return "markdown-vendor";
          if (id.includes("lucide-react")) return "icons";
        },
      },
    },
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
