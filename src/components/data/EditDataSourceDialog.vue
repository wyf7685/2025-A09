<script setup lang="ts">
import type { DataSourceMetadataWithID } from '@/types';
import { ElButton, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus';
import { ref, watch } from 'vue';

// 使用 defineModel 实现对话框可见性双向绑定
const visible = defineModel<boolean>('visible', { required: true });

// 定义组件属性
const props = defineProps<{
  datasource: DataSourceMetadataWithID | null;
}>();

// 定义组件事件
const emit = defineEmits<{
  save: [name: string, description: string];
}>();

// 编辑表单数据
const editForm = ref({
  name: '',
  description: ''
});

// 监听数据源变化，更新表单数据
watch(() => props.datasource, (newVal) => {
  if (newVal) {
    editForm.value.name = newVal.name;
    editForm.value.description = newVal.description || '';
  }
}, { immediate: true });

// 保存编辑
const saveEdit = () => {
  emit('save', editForm.value.name, editForm.value.description);
};
</script>

<template>
  <el-dialog v-model="visible" title="编辑数据源信息" width="500px" :before-close="() => visible = false">
    <el-form :model="editForm" label-width="80px">
      <el-form-item label="名称">
        <el-input v-model="editForm.name" placeholder="请输入数据源名称" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="editForm.description" type="textarea" placeholder="请输入数据源描述" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.el-dialog {
  :deep(.el-dialog__header) {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 16px 16px 0 0;
    padding: 20px 24px;

    .el-dialog__title {
      font-weight: 600;
      font-size: 18px;
      color: white;
    }
  }

  :deep(.el-dialog__body) {
    padding: 24px;
  }

  :deep(.el-dialog__footer) {
    border-top: 1px solid #e5e7eb;
    padding: 16px 24px;

    .el-button {
      border-radius: 20px;
      padding: 8px 20px;
      font-weight: 500;
    }
  }
}
</style>
