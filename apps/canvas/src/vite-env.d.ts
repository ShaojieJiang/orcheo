/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ORCHEO_BACKEND_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
