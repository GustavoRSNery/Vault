/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    // `node` e não `jsdom` de propósito: o núcleo da lib de gráficos é função
    // pura que devolve geometria, e testá-lo não exige DOM. Um teste de
    // componente, quando houver, declara o ambiente no próprio arquivo com
    // `// @vitest-environment jsdom`.
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
  server: {
    port: 5173,
    proxy: {
      // O front fala com /api e o Vite encaminha ao backend: sem CORS em dev
      // e sem URL absoluta espalhada pelo código.
      '/api': { target: 'http://127.0.0.1:8777', changeOrigin: true },
    },
  },
})
