import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
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
