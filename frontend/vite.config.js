import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],

    server: {
        host: "0.0.0.0",
        port: 5173,
        strictPort: false,
        open: false,
        proxy: {
            // Dev-only: forward /api/* to the backend so the browser sees same-origin.
            "/api": {
                target: process.env.VITE_BACKEND_URL || "http://localhost:5001",
                changeOrigin: true,
                secure: false,
                rewrite: (path) => path.replace(/^\/api/, ""),
            },
        },
    },

    preview: {
        host: "0.0.0.0",
        port: 4173,
        strictPort: false,
    },

    build: {
        outDir: "dist",
        emptyOutDir: true,
        sourcemap: false,
        target: "es2020",
        chunkSizeWarningLimit: 1000,
        rollupOptions: {
            output: {
                manualChunks: {
                    react: ["react", "react-dom"],
                },
            },
        },
    },

    esbuild: {
        jsx: "automatic",
    },

    optimizeDeps: {
        include: ["react", "react-dom"],
    },
});