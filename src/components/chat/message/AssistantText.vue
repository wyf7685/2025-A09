<script lang="ts" setup>
import { formatMessage } from '@/utils/tools';
import { onMounted, ref, watch } from 'vue';

const props = defineProps<{
  md: string;
}>();

const formatted = ref<string>('');

const format = async (md: string): Promise<void> => {
  formatted.value = md ? await formatMessage(md) : '';
};

onMounted(async () => await format(props.md));

watch(() => props.md,
  async (newVal) => await format(newVal),
  { immediate: true, deep: true }
);
</script>

<template>
  <div v-if="formatted" class="markdown-body" v-html="formatted"></div>
</template>

<style scoped>
/* 覆盖一些 GitHub 样式以更好地适应聊天界面 */
:deep(.markdown-body) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: transparent;
  font-size: 14px;
  color: #374151;

  /* 调整代码块样式 */
  pre {
    background-color: #f6f8fa;
    border-radius: 8px;
    padding: 12px;
    border: 1px solid #e1e5e9;
    overflow-x: auto;
  }

  code {
    background-color: #f6f8fa;
    padding: 2px 4px;
    border-radius: 4px;
    font-size: 13px;
  }

  /* 调整表格样式 */
  table {
    display: table;
    width: 100%;
    overflow-x: auto;
    border-collapse: collapse;
    margin: 12px 0;
  }

  table th,
  table td {
    padding: 8px 12px;
    border: 1px solid #e1e5e9;
    text-align: left;
  }

  table th {
    background-color: #f6f8fa;
    font-weight: 600;
  }

  /* 调整图片最大宽度 */
  img {
    max-width: 100%;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  /* 调整标题样式 */
  h1,
  h2,
  h3,
  h4,
  h5,
  h6 {
    color: #1f2937;
    font-weight: 600;
  }

  /* 调整链接样式 */
  a {
    color: #10b981;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  /* 调整列表样式 */
  ul,
  ol {
    margin: 8px 0;
    padding-left: 20px;
  }

  li {
    margin: 4px 0;
  }

  /* 调整引用样式 */
  blockquote {
    margin: 12px 0;
    padding: 8px 12px;
    background-color: #f9fafb;
    border-left: 4px solid #10b981;
    border-radius: 4px;
  }
}
</style>
