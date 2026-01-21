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
  // These packages are CommonJS but imported by ESM modules, causing issues in dev server
  optimizeDeps: {
    include: [
      // Used by zustand, swr, @radix-ui
      'use-sync-external-store/shim',
      'use-sync-external-store/shim/with-selector',
      // Used by react-split, react-big-calendar, etc.
      'prop-types',
      'react-split',
      // Used by @rjsf/utils and @rjsf/validator-ajv8
      'jsonpointer',
      'json-schema-merge-allof',
      'react-is',
      'ajv',
      'ajv-formats',
      // Used by react-big-calendar, antd, etc.
      'dayjs',
      'invariant',
      'dom-helpers',
      // Lodash submodules used by @rjsf
      'lodash/get',
      'lodash/set',
      'lodash/has',
      'lodash/omit',
      'lodash/pick',
      'lodash/merge',
      'lodash/cloneDeep',
      'lodash/isEmpty',
      'lodash/isObject',
      'lodash/isString',
      'lodash/isNumber',
      'lodash/isNil',
      'lodash/isPlainObject',
      'lodash/forEach',
      'lodash/toPath',
      'lodash/uniqueId',
      'lodash/keys',
      'lodash/union',
      'lodash/uniq',
      'lodash/times',
      'lodash/reduce',
      'lodash/transform',
      'lodash/difference',
      'lodash/flattenDeep',
      'lodash/isEqualWith',
      'lodash/setWith',
      'lodash/pickBy',
      'lodash/unset',
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
