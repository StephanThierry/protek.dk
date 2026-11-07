import { defineConfig } from 'vite';

// Relativ base, så buildet virker både i roden af protek.dk og i en undermappe.
export default defineConfig({
  base: './',
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0, chunkSizeWarningLimit: 900 },
});
