<script setup lang="ts">
import { ElButton, ElCheckbox, ElDescriptions, ElDescriptionsItem, ElDialog, ElTable, ElTableColumn, ElTag } from 'element-plus';
import { ref, watch } from 'vue';
import type { MLModel } from '@/types/model';

const props = defineProps<{
  models: MLModel[];
  selectedModels: string[];
}>();

const emit = defineEmits<{
  select: [modelId: string];
}>();

// 选择状态
const selection = ref<Record<string, boolean>>({});

// 更新选择状态
watch(
  () => props.selectedModels,
  (newSelectedModels) => {
    const newSelection: Record<string, boolean> = {};
    for (const modelId of newSelectedModels) {
      newSelection[modelId] = true;
    }
    selection.value = newSelection;
  },
  { immediate: true }
);

// 获取行的类名
const getRowClass = ({ row }: { row: MLModel; }) => {
  return selection.value[row.id] ? 'selected-row' : '';
};

// 行点击处理
const handleRowClick = (row: MLModel) => {
  selection.value[row.id] = !selection.value[row.id];
  emit('select', row.id);
};

// 格式化日期时间
const formatDateTime = (dateTimeStr: string | undefined) => {
  if (!dateTimeStr) return '未知时间';
  try {
    const date = new Date(dateTimeStr);
    return date.toLocaleString('zh-CN');
  } catch (e) {
    return dateTimeStr;
  }
};

// 将指标对象转换为表格数据
const metricsToTable = (metrics: Record<string, number> | undefined) => {
  if (!metrics) return [];
  return Object.entries(metrics).map(([metric, value]) => ({
    metric,
    value: typeof value === 'number' ? value.toFixed(4) : String(value),
  }));
};

// 将超参数对象转换为表格数据
const hyperparamsToTable = (hyperparams: Record<string, any> | undefined) => {
  if (!hyperparams) return [];
  return Object.entries(hyperparams).map(([param, value]) => ({
    param,
    value: JSON.stringify(value),
  }));
};

// 模型详情
const detailsVisible = ref(false);
const currentModel = ref<MLModel | null>(null);

// 显示模型详情
const showModelDetails = (model: MLModel) => {
  currentModel.value = model;
  detailsVisible.value = true;
};
</script>

<template>
  <div class="model-list">
    <el-table
      :data="models"
      style="width: 100%"
      @row-click="handleRowClick"
      :row-class-name="getRowClass">
      <el-table-column width="50">
        <template #default="scope">
          <el-checkbox
            v-model="selection[scope.row.id]"
            @change="() => $emit('select', scope.row.id)"
            @click.stop />
        </template>
      </el-table-column>
      <el-table-column prop="name" label="模型名称" min-width="120">
        <template #default="scope">
          <div class="model-name">
            {{ scope.row.name || '未命名模型' }}
            <el-tag v-if="scope.row.is_registered" size="small" type="success">已注册</el-tag>
          </div>
          <div class="model-id text-secondary">ID: {{ scope.row.id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="model_type" label="类型" min-width="100" />
      <el-table-column prop="created_at" label="创建时间" min-width="100">
        <template #default="scope">
          {{ formatDateTime(scope.row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="scope">
          <el-button
            type="primary"
            link
            @click.stop="showModelDetails(scope.row)"
            text>
            详情
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 模型详情对话框 -->
    <el-dialog v-model="detailsVisible" title="模型详情" width="50%" :destroy-on-close="true">
      <div v-if="currentModel" class="model-details">
        <h3>基本信息</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="模型名称">{{ currentModel.name || '未命名模型' }}</el-descriptions-item>
          <el-descriptions-item label="模型类型">{{ currentModel.type }}</el-descriptions-item>
          <el-descriptions-item label="目标变量">{{ currentModel.target_column }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(currentModel.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="源会话" :span="2">
            {{ currentModel.session_name || '未知会话' }}
          </el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">
            {{ currentModel.description || '无描述' }}
          </el-descriptions-item>
        </el-descriptions>

        <h3 class="mt-4">性能指标</h3>
        <el-table :data="metricsToTable(currentModel.metrics)" border stripe>
          <el-table-column prop="metric" label="指标" />
          <el-table-column prop="value" label="值" />
        </el-table>

        <h3 class="mt-4">特征列表 ({{ currentModel.features?.length || 0 }})</h3>
        <el-tag v-for="feature in currentModel.features" :key="feature" class="feature-tag">
          {{ feature }}
        </el-tag>

        <template v-if="currentModel.hyperparams && Object.keys(currentModel.hyperparams).length > 0">
          <h3 class="mt-4">超参数</h3>
          <el-table :data="hyperparamsToTable(currentModel.hyperparams)" border stripe>
            <el-table-column prop="param" label="参数" />
            <el-table-column prop="value" label="值" />
          </el-table>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.model-name {
  font-weight: 500;
}

.text-secondary {
  color: #909399;
  font-size: 0.85em;
}

.selected-row {
  background-color: var(--el-color-primary-light-9);
}

.model-details h3 {
  margin-top: 20px;
  margin-bottom: 10px;
  font-weight: 500;
}

.feature-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.mt-4 {
  margin-top: 16px;
}
</style>
