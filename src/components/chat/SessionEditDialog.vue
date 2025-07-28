<script setup lang="ts">
import { ElButton, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus';
import { ref, watch } from 'vue';

// 使用 defineModel 实现双向绑定对话框的可见性
const visible = defineModel<boolean>('visible', { required: true });

// 使用 defineModel 实现双向绑定会话名称
const sessionName = defineModel<string>('sessionName', { required: true });

defineProps<{
  sessionId: string; // 正在编辑的会话ID
}>();

const emit = defineEmits<{
  'save': []; // 保存会话编辑
}>();

// 本地编辑状态
const localSessionName = ref('');

// 监听 sessionName 的变化，同步到本地状态
watch(() => sessionName.value, (newName) => {
  localSessionName.value = newName;
}, { immediate: true });

// 关闭对话框
const closeDialog = () => {
  visible.value = false;
};

// 保存编辑
const saveEdit = () => {
  // 更新父组件中的 sessionName
  sessionName.value = localSessionName.value.trim();
  // 触发保存事件
  emit('save');
};

// 重置表单
const resetForm = () => {
  localSessionName.value = sessionName.value;
};

// 在对话框关闭时重置表单
watch(() => visible.value, (newVisible) => {
  if (newVisible) {
    resetForm();
  }
});
</script>

<template>
  <el-dialog v-model="visible" title="编辑会话名称" width="400px" destroy-on-close @close="resetForm">
    <div class="edit-session-dialog">
      <el-form :model="{ name: localSessionName }" label-position="top">
        <el-form-item label="会话名称">
          <el-input v-model="localSessionName" placeholder="请输入会话名称" maxlength="50" show-word-limit clearable
            autofocus />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" @click="saveEdit" :disabled="!localSessionName.trim()">
          保存
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.edit-session-dialog {
  padding: 10px;

  .el-form-item__label {
    font-weight: 500;
    color: #374151;
  }

  .el-input {
    .el-input__wrapper {
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
      transition: all 0.3s ease;

      &:hover,
      &:focus {
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1), 0 0 0 1px #10b981;
      }
    }
  }
}
</style>
