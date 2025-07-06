<template>
  <div class="empty-state">
    <div class="empty-content">
      <el-icon class="empty-icon" :size="iconSize">
        <component :is="iconComponent" />
      </el-icon>
      <div class="empty-title">{{ title }}</div>
      <div class="empty-description" v-if="description">{{ description }}</div>
      <div class="empty-actions" v-if="$slots.actions">
        <slot name="actions"></slot>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { 
  DocumentRemove, 
  FolderRemove, 
  DataLine,
  Connection,
  Box,
  ChatLineRound 
} from '@element-plus/icons-vue'

const props = defineProps({
  type: {
    type: String,
    default: 'default',
    validator: (value) => [
      'default', 'data', 'folder', 'document', 
      'connection', 'model', 'chat'
    ].includes(value)
  },
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  iconSize: {
    type: Number,
    default: 64
  }
})

const iconComponent = computed(() => {
  const icons = {
    default: DocumentRemove,
    data: DataLine,
    folder: FolderRemove,
    document: DocumentRemove,
    connection: Connection,
    model: Box,
    chat: ChatLineRound
  }
  return icons[props.type] || icons.default
})
</script>

<style scoped lang="scss">
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  padding: 40px 20px;

  .empty-content {
    text-align: center;
    max-width: 400px;

    .empty-icon {
      color: #c0c4cc;
      margin-bottom: 20px;
    }

    .empty-title {
      font-size: 16px;
      color: #909399;
      font-weight: 500;
      margin-bottom: 12px;
    }

    .empty-description {
      font-size: 14px;
      color: #c0c4cc;
      line-height: 1.5;
      margin-bottom: 24px;
    }

    .empty-actions {
      display: flex;
      justify-content: center;
      gap: 12px;
    }
  }
}
</style>
