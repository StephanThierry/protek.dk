import { defineConfig } from 'vite';

// Relativ base, så det byggede site virker under protek.dk/newdesign/ (og alle andre undermapper).
export default defineConfig({
  base: './',
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0, chunkSizeWarningLimit: 900 },
});
