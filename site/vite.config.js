import { defineConfig } from 'vite';

// Relative base so the build works both at the protek.dk root and in a subfolder.
export default defineConfig({
  base: './',
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0, chunkSizeWarningLimit: 900 },
});
