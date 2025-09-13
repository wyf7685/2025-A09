<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="保存当前流程"
    width="500px"
    :close-on-click-modal="false"
    :before-close="handleClose"
  >
    <el-form :model="form" label-width="100px" ref="formRef" :rules="rules">
      <el-form-item label="流程名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入工作流名称" />
      </el-form-item>
      <el-form-item label="流程描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 5 }"
          placeholder="请输入工作流描述（可选）"
        />
      </el-form-item>
      <el-alert
        v-if="toolCallCount > 0"
        type="success"
        :title="`已检测到 ${toolCallCount} 个工具调用`"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else
        type="warning"
        title="未检测到工具调用，保存的工作流将无法执行"
        show-icon
        :closable="false"
      />
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">
          保存流程
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, defineEmits, defineProps, computed, watch } from 'vue';
import type { FormInstance, FormRules } from 'element-plus';
import { useWorkflowStore } from '@/stores/workflow';
import type { ChatMessage } from '@/types';
import { ElMessage } from 'element-plus';

const props = defineProps<{
  visible: boolean;
  messages: ChatMessage[];
  sessionId: string;
}>();

const emit = defineEmits(['update:visible', 'saved']);

const workflowStore = useWorkflowStore();
const saving = ref(false);
const formRef = ref<FormInstance>();

const form = ref({
  name: '',
  description: '',
});

const rules: FormRules = {
  name: [
    { required: true, message: '请输入工作流名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度应为2-50个字符', trigger: 'blur' }
  ],
};

// 计算工具调用数量
const toolCallCount = computed(() => {
  let count = 0;
  for (const message of props.messages) {
    if (message.type === 'assistant' && message.tool_calls) {
      count += Object.keys(message.tool_calls).length;
    }
  }
  return count;
});

// 保存工作流
const handleSave = async () => {
  if (!formRef.value) return;

  await formRef.value.validate(async (valid) => {
    if (!valid) return;

    saving.value = true;
    try {
      await workflowStore.saveWorkflow({
        name: form.value.name,
        description: form.value.description,
        session_id: props.sessionId,
        messages: props.messages
      });

      ElMessage.success('工作流保存成功');
      emit('saved');
      handleClose();
    } catch (error) {
      console.error('保存工作流失败:', error);
      ElMessage.error('保存工作流失败');
    } finally {
      saving.value = false;
    }
  });
};

// 关闭对话框
const handleClose = () => {
  emit('update:visible', false);
  // 重置表单
  form.value = {
    name: '',
    description: '',
  };
};

watch(() => props.visible, (newVal) => {
  if (newVal && props.messages.length > 0) {
    // 如果有消息，使用最后一条用户消息作为默认工作流名称
    for (let i = props.messages.length - 1; i >= 0; i--) {
      if (props.messages[i].type === 'user') {
        const content = props.messages[i].content as string;
        form.value.name = content.length > 20 ? content.substring(0, 20) + '...' : content;
        break;
      }
    }
  }
});
</script>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  width: 100%;
}
</style>
