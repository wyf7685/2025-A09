<script setup lang="ts">
import type { AnalyzeDataQualityState, CleaningAction, CleaningStep, CleaningSuggestion } from '@/types/cleaning';
import { Icon } from '@iconify/vue';
import { ElButton, ElCard, ElDialog, ElMessage, ElResult, ElTag } from 'element-plus';
import { ref } from 'vue';

// 导入项目中统一的API实例
import { cleaningAPI } from '@/utils/api';

// 当前步骤的双向绑定
const step = defineModel<CleaningStep>('step', { required: true });

// 定义组件属性
const props = defineProps<{
  analysisResult: AnalyzeDataQualityState | null;
  selectedCleaningActions: CleaningAction[];
  cleaningSuggestions: CleaningSuggestion[];
  cleanedFileId?: string;
}>();

// 定义组件事件
const emit = defineEmits<{
  complete: [];
  skipAndUpload: [];
  analyze: [];
}>();

// 代码查看相关状态
const showCodeDialog = ref(false);
const generatedCode = ref('');
const isLoadingCode = ref(false);

// 完成清洗
const completeCleaningAndUpload = () => emit('complete');

// 跳过清洗直接上传
const skipAnalysisAndUpload = () => emit('skipAndUpload');

// 重新分析
const startAnalysis = () => emit('analyze');

// 查看生成的清洗代码
const viewGeneratedCode = async () => {
  if (!props.cleanedFileId) {
    ElMessage.warning('没有找到清洗文件ID');
    return;
  }

  console.log('开始获取生成代码，文件ID:', props.cleanedFileId);
  isLoadingCode.value = true;
  showCodeDialog.value = true;

  try {
    console.log('调用API获取生成代码...');
    const response = await cleaningAPI.getGeneratedCode(props.cleanedFileId);
    console.log('API响应:', response);

    if (response.success && response.generated_code) {
      generatedCode.value = response.generated_code;
      ElMessage.success('成功获取生成的清洗代码');
    } else {
      generatedCode.value = '暂无生成的代码';
      ElMessage.warning(response.error || '暂无生成的代码');
    }
  } catch (error) {
    console.error('获取生成代码失败:', error);
    generatedCode.value = '获取代码失败，请稍后重试';
    ElMessage.error('获取代码失败');
  } finally {
    isLoadingCode.value = false;
  }
};
</script>

<template>
  <div class="complete-status">
    <el-result status="success" title="处理完成" :sub-title="analysisResult?.data_uploaded ?
      '数据已成功上传到Dremio，您可以在数据源列表中查看' :
      '数据处理完成，请选择操作'">
      <template #icon>
        <Icon icon="material-symbols:task-alt-rounded" width="80" height="80" color="#67C23A" />
      </template>
      <template #extra>
        <div class="complete-actions">
          <el-button type="primary" @click="completeCleaningAndUpload" size="large"
            v-if="analysisResult?.data_uploaded">
            <Icon icon="material-symbols:check-circle-outline-rounded" width="18" height="18"
              style="margin-right: 4px;" />
            关闭并查看数据源列表
          </el-button>

          <el-button type="primary" @click="skipAnalysisAndUpload" size="large" v-if="!analysisResult?.data_uploaded">
            <Icon icon="material-symbols:cloud-upload-outline-rounded" width="18" height="18"
              style="margin-right: 4px;" />
            立即上传数据
          </el-button>

          <el-button @click="startAnalysis" size="large">
            <Icon icon="material-symbols:refresh-rounded" width="18" height="18" style="margin-right: 4px;" />
            重新分析数据质量
          </el-button>

          <el-button @click="step = 'cleaning'" v-if="cleaningSuggestions.length > 0 && !analysisResult?.data_uploaded"
            size="large">
            <Icon icon="material-symbols:edit-outline-rounded" width="18" height="18" style="margin-right: 4px;" />
            重新选择清洗操作
          </el-button>

          <el-button @click="viewGeneratedCode" size="large"
            v-if="cleanedFileId"
            type="info">
            <Icon icon="material-symbols:code-rounded" width="18" height="18" style="margin-right: 4px;" />
            查看生成的清洗代码
          </el-button>
        </div>

        <div class="complete-summary" v-if="selectedCleaningActions.length > 0">
          <el-card class="summary-card">
            <template #header>
              <span>已执行的清洗操作摘要</span>
            </template>
            <div class="summary-list">
              <div v-for="(action, index) in selectedCleaningActions" :key="index" class="summary-item">
                <el-tag type="primary" size="small">{{ action.type }}</el-tag>
                <span>{{ action.column }}</span>
              </div>
            </div>
          </el-card>
        </div>
      </template>
    </el-result>

    <!-- 代码查看对话框 -->
    <el-dialog v-model="showCodeDialog" title="生成的清洗代码" width="80%" class="code-dialog">
      <div class="code-content">
        <div v-if="isLoadingCode" class="loading-text">
          正在加载代码...
        </div>
        <pre v-else class="code-block"><code>{{ generatedCode }}</code></pre>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showCodeDialog = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.complete-status {
  .complete-actions {
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 24px;

    .el-button {
      border-radius: 8px;
      padding: 12px 24px;
      font-weight: 500;
    }
  }

  .complete-summary {
    max-width: 500px;
    margin: 0 auto;

    .summary-card {
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);

      :deep(.el-card__header) {
        background: #f9fafb;
        font-weight: 600;
        color: #1f2937;
      }

      .summary-list {
        .summary-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 8px 0;
          border-bottom: 1px solid #e5e7eb;

          &:last-child {
            border-bottom: none;
          }

          .el-tag {
            border-radius: 4px;
          }

          span {
            font-size: 14px;
            color: #374151;
          }
        }
      }
    }
  }
}

/* 代码对话框样式 */
.code-dialog {
  :deep(.el-dialog__body) {
    padding: 0;
  }

  .code-content {
    .loading-text {
      text-align: center;
      padding: 40px;
      color: #666;
      font-size: 14px;
    }

    .code-block {
      background: #1f2937;
      color: #f9fafb;
      border-radius: 0;
      padding: 20px;
      font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
      font-size: 13px;
      line-height: 1.5;
      margin: 0;
      white-space: pre-wrap;
      overflow-x: auto;
      max-height: 500px;
      overflow-y: auto;

      code {
        color: inherit;
        background: transparent;
        font-family: inherit;
      }
    }
  }

  .dialog-footer {
    text-align: right;
    padding: 16px 24px;
    border-top: 1px solid #e5e7eb;
  }
}
</style>
