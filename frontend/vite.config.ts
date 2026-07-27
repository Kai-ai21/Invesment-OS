/// <reference types="vitest/config" />
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // The triple-slash reference above is what types `test` here — it is the form the
  // Vitest docs give when defineConfig is imported from vite itself rather than from
  // vitest/config.
  test: {
    // Components need a DOM.
    environment: 'jsdom',
    // `describe`/`it`/`expect` without importing them in every file.
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
