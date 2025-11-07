<script setup lang="ts">
import { reportAPI } from '@/utils/api';
import { ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElMessage } from 'element-plus';
import { ref, watch } from 'vue';

const visible = defineModel<boolean>('visible', { required: true });

const emit = defineEmits<{
  'template-uploaded': [];
}>();

// 模板表单数据
const templateName = ref('');
const templateDescription = ref('');
const templateContent = ref('');

watch(() => visible.value, (newValue) => {
  if (newValue) {
    // 重置表单数据
    templateName.value = '';
    templateDescription.value = '';
    templateContent.value = '';
  }
});

// 上传模板
const uploadTemplate = async () => {
  if (!templateName.value.trim() || !templateDescription.value.trim() || !templateContent.value.trim()) {
    ElMessage.warning('请填写完整的模板信息');
    return;
  }

  try {
    const blob = new Blob([templateContent.value], { type: 'text/plain' });
    const file = new File([blob], `${templateName.value}.txt`, { type: 'text/plain' });

    await reportAPI.uploadTemplate(templateName.value, templateDescription.value, file);
    ElMessage.success('模板上传成功');

    emit('template-uploaded');
    visible.value = false;
  } catch (error: unknown) {
    console.error('上传模板失败:', error);
    ElMessage.error('上传模板失败: ' + ((error as { message?: string; })?.message || error));
  }
};
</script>

<template>
  <el-dialog v-model="visible" title="上传报告模板" width="60%" :close-on-click-modal="false" :close-on-press-escape="false">
    <el-form label-width="120px">
      <el-form-item label="模板名称">
        <el-input v-model="templateName" placeholder="请输入模板名称"></el-input>
      </el-form-item>
      <el-form-item label="模板描述">
        <el-input v-model="templateDescription" type="textarea" placeholder="请输入模板描述"></el-input>
      </el-form-item>
      <el-form-item label="模板内容">
        <el-input v-model="templateContent" type="textarea" placeholder="请输入模板内容，使用 {conversation} 作为对话内容的占位符"
          :rows="10"></el-input>
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="uploadTemplate">上传</el-button>
      </span>
    </template>
  </el-dialog>
</template>
