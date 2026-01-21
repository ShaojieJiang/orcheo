/// <reference types="vitest" />
import { defineConfig, mergeConfig } from 'vitest/config'
import path from 'path'
import { fileURLToPath } from 'url'
import viteConfig from './vite.config'

// ES Module equivalent of __dirname
const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Extend vite.config.ts with test-specific configuration
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: './src/setupTests.ts',
      alias: {
        '@openai/chatkit-react': path.resolve(
          __dirname,
          './src/test-utils/chatkit-stub.ts',
        ),
      },
    },
  })
)
