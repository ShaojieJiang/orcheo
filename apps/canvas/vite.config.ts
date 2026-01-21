import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

// ES Module equivalent of __dirname
const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@lib': path.resolve(__dirname, './src/lib'),
      '@design-system': path.resolve(__dirname, './src/design-system'),
      '@features': path.resolve(__dirname, './src/features'),
    }
  },
  // Fix for CJS/ESM compatibility issues with React 19
  optimizeDeps: {
    include: [
      'use-sync-external-store/shim',
      'use-sync-external-store/shim/with-selector',
      'prop-types',
      'react-split',
    ]
  },
  build: {
    commonjsOptions: {
      include: [/use-sync-external-store/, /node_modules/]
    }
  },
  server: {
    allowedHosts: [
      'orcheo-canvas.ai-colleagues.com'
    ]
  }
})
