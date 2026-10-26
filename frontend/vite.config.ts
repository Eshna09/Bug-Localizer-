import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // SSE streams can take 5+ minutes with local LLMs.
        // Set both timeouts to 10 minutes to prevent the proxy
        // from closing the connection mid-stream.
        timeout: 600000,
        proxyTimeout: 600000,
      },
    },
  },
})
