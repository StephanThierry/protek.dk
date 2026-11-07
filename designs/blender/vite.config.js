import { defineConfig } from 'vite';

// Relative base so the built site works under protek.dk/blender/ (and any other subfolder).
export default defineConfig({
  base: './',
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0, chunkSizeWarningLimit: 900 },
});
