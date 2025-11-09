/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_ICP_NUMBER: string;
  readonly VITE_POLICE_NUMBER: string;
  readonly VITE_COMPANY_NAME: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
