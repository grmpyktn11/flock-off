import { defineConfig } from "vite";

// Relative base so the same build works at flock-off.github.io/flock-off/
// and on any other static host.
export default defineConfig({
  base: "./",
});
