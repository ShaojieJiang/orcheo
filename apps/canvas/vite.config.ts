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
  // Force Vite to pre-bundle all dependencies to handle CJS->ESM conversion
  optimizeDeps: {
    // Force pre-bundling of all dependencies
    force: true,
    // Exclude nothing - bundle everything
    exclude: [],
    // Explicitly include problematic nested imports
    include: [
      'use-sync-external-store/shim',
      'use-sync-external-store/shim/with-selector',
      'react-split > prop-types',
      'ajv/dist/standalone',
    ],
    // Scan all entry points
    esbuildOptions: {
      // Ensure proper CJS to ESM conversion
      mainFields: ['module', 'main'],
    }
  },
  build: {
    commonjsOptions: {
      // Transform all CJS modules in node_modules
      include: [/node_modules/],
      // Use proper named exports detection
      requireReturnsDefault: 'auto',
    }
  },
  server: {
    allowedHosts: [
      'orcheo-canvas.ai-colleagues.com'
    ],
    // Force dependency pre-bundling on server start
    warmup: {
      clientFiles: ['./src/**/*.tsx', './src/**/*.ts']
    }
  },
  // Ensure SSR also handles CJS properly
  ssr: {
    noExternal: true
  }
})
