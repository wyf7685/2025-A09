import App from '@/App.vue';
import router from '@/router';
import 'element-plus/dist/index.css';
import { createPinia } from 'pinia';
import { createApp } from 'vue';
import './assets/styles/main.scss';

const app = createApp(App);

app.use(createPinia());
app.use(router);

app.mount('#app');
