import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./frontend/src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./frontend/src/setupTests.ts"],
    include: ["frontend/src/**/*.{test,spec}.{ts,tsx}"],
  },
});



