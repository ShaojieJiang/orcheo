/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ORCHEO_BACKEND_URL?: string;
  readonly VITE_CHATKIT_API_URL?: string;
  readonly VITE_CHATKIT_DOMAIN_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
