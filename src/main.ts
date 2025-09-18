import App from '@/App.vue';
import router from '@/router';
import 'element-plus/dist/index.css';
import { createPinia } from 'pinia';
import { createApp } from 'vue';
import './assets/styles/main.scss';

// Iconify configuration
import { addAPIProvider } from '@iconify/vue';
addAPIProvider('', {
  resources: ['https://api.iconify.design'],
});

const app = createApp(App);

app.use(createPinia());
app.use(router);

app.mount('#app');
