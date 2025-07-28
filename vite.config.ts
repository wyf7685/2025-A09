import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';
import AutoImport from 'unplugin-auto-import/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import Components from 'unplugin-vue-components/vite';
import { defineConfig } from 'vite';
import vueDevTools from 'vite-plugin-vue-devtools';

export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
      },
      output: {
        assetFileNames: (assetInfo) => {
          // 对于 favicon.ico，保持其在根目录中
          if (assetInfo.names.includes('favicon.ico')) {
            return 'favicon.ico';
          }
          return 'assets/[name]-[hash][extname]';
        },
        manualChunks: {
          vendor: ['vue', 'vue-router', 'axios', 'pinia'],
          // echarts: ['echarts'],  // unused
          marked: ['marked'],
          'element-plus': ['element-plus'],
          'element-plus-icons': ['@element-plus/icons-vue'],
        },
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {},
    },
  },
});
