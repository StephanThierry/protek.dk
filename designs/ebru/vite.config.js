import { defineConfig } from 'vite';

// Relative base so the built site works under protek.dk/designs/<name>/ (and any other subfolder).
export default defineConfig({
  base: './',
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0, chunkSizeWarningLimit: 900 },
});
