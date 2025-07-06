<script setup lang="ts">
import { ref } from 'vue'

const msg = ref("Hello Vue 3!")
</script>

<template>
  <div class="app">
    <h1>{{ msg }}</h1>
    <p>如果你能看到这个，说明 Vue 应用正常运行了！</p>
    <RouterView />
  </div>
</template>

<style scoped>
.app {
  padding: 20px;
  text-align: center;
  font-family: Arial, sans-serif;
}

h1 {
  color: #42b883;
  margin-bottom: 20px;
}

p {
  color: #666;
  margin-bottom: 30px;
}
</style>