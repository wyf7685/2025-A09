<script lang="ts" setup>
import { formatMessage } from '@/utils/tools';
import { onMounted, ref, watch } from 'vue';

const props = defineProps<{
  md: string;
}>();

const formatted = ref<string>('');

onMounted(async () => {
  if (props.md) {
    formatted.value = await formatMessage(props.md);
  }
});

watch(() => props.md, async (newVal) => {
  if (newVal) {
    formatted.value = await formatMessage(newVal);
  } else {
    formatted.value = '';
  }
}, {
  immediate: true,
  deep: true
});
</script>

<template>
  <div v-if="formatted" class="markdown-body" v-html="formatted"></div>
</template>

<style scoped>
/* 覆盖一些 GitHub 样式以更好地适应聊天界面 */
:deep(.markdown-body) {
  font-family: inherit;
  background-color: transparent;
  font-size: 14px;

  /* 调整代码块样式 */
  pre {
    background-color: #f6f8fa;
    border-radius: 6px;
  }

  /* 调整表格样式 */
  table {
    display: table;
    width: 100%;
    overflow-x: auto;
  }

  /* 调整图片最大宽度 */
  img {
    max-width: 100%;
  }
}

.rotating {
  animation: rotating 2s linear infinite;
}
</style>
