import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

/**
 * Vitest config for the BDGO frontend.
 *
 * The Next.js build pipeline doesn't run tests; this is a separate
 * vitest pass that exercises pure functions, hooks, and components in
 * isolation under jsdom. Browser/E2E coverage is a future story —
 * vitest's job here is fast feedback on logic regressions during
 * development and CI.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    css: false, // skip CSS parsing — we don't snapshot styles
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
  resolve: {
    alias: {
      // Mirror Next.js's tsconfig path alias so `@/lib/...` resolves under
      // vitest the same way it resolves at runtime.
      "@": path.resolve(__dirname, "src"),
    },
  },
});
