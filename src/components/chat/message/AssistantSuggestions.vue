<script setup lang="ts">
import { ElButton } from 'element-plus';

defineProps<{
  suggestions: string[];
}>();

const emit = defineEmits<{
  'set': [suggestion: string];
}>();

// 工具函数：去除markdown粗体、冒号和多余空格，只取建议标题部分
const stripSuggestion = (s: string) => {
  const clean = s.replace(/\*\*/g, '').trim();
  const idx = clean.indexOf('：');
  return idx !== -1 ? clean.slice(0, idx) : clean;
};
</script>

<template>
  <div class="suggestion-buttons">
    <el-button v-for="(suggestion, index) in suggestions" :key="index" size="small"
      @click="emit('set', stripSuggestion(suggestion))" style="margin: 4px 4px 0 0;">
      {{ stripSuggestion(suggestion) }}
    </el-button>
  </div>
</template>

<style lang="scss" scoped>
.suggestion-buttons {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  .el-button {
    border-radius: 20px;
    font-size: 12px;
    padding: 4px 12px;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    color: #6b7280;
    transition: all 0.2s ease;

    &:hover {
      background: #e5e7eb;
      color: #374151;
      border-color: #d1d5db;
      transform: translateY(-1px);
    }
  }
}
</style>
