<script setup lang="ts">
import { useSessionStore } from '@/stores/session';
import type { ReportTemplate } from '@/types/report';
import { reportAPI } from '@/utils/api';
import { Download, Upload } from '@element-plus/icons-vue';
import {
  ElButton, ElDialog, ElIcon, ElMessage, ElMessageBox, ElOption,
  ElSelect, ElTable, ElTableColumn, ElTabPane, ElTabs, ElTag
} from 'element-plus';
import { computed, ref, watch } from 'vue';
import TemplateUploadDialog from './TemplateUploadDialog.vue';
import { formatMessage } from '@/utils/tools';

const visible = defineModel<boolean>('visible', { required: true });

// 状态变量
const activeTab = ref('generate');
const isGeneratingReport = ref(false);
const reportTemplates = ref<ReportTemplate[]>([]);
const selectedTemplateId = ref<string>('default');
const generatedReport = ref<string>('');
const formattedReport = ref<string>('');
const reportFigures = ref<string[]>([]);
const reportTitle = ref<string>('');
const viewingTemplate = ref<ReportTemplate | null>(null);
const uploadTemplateDialogVisible = ref(false);

const sessionStore = useSessionStore();
const currentSessionName = computed(() => {
  const session = sessionStore.sessions.find(s => s.id === sessionStore.currentSessionId);
  return session ? session.name : '未命名会话';
});

// 监听visible变化，初始化数据
watch(() => visible.value, async (newValue) => {
  if (newValue) {
    // 重置状态
    activeTab.value = 'generate';
    viewingTemplate.value = null;
    generatedReport.value = '';
    reportFigures.value = [];

    await loadReportTemplates();
  }
});

// 加载报告模板
const loadReportTemplates = async () => {
  try {
    const result = await reportAPI.getTemplates();
    reportTemplates.value = result;
  } catch (error) {
    console.error('加载报告模板失败:', error);
    ElMessage.error('加载报告模板失败');
  }
};

// 生成报告
const generateReport = async () => {
  if (isGeneratingReport.value) return;
  if (!sessionStore.currentSessionId) {
    ElMessage.warning('未选择会话');
    return;
  }

  isGeneratingReport.value = true;
  try {
    const result = await reportAPI.generateReport(
      sessionStore.currentSessionId,
      selectedTemplateId.value === 'default' ? undefined : selectedTemplateId.value
    );
    generatedReport.value = result.report;
    formattedReport.value = await formatMessage(result.report);
    reportFigures.value = result.figures || [];
    reportTitle.value = result.report_title || currentSessionName.value;
    ElMessage.success(`报告生成成功！使用模板：${result.template_used}`);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } catch (error: any) {
    console.error('生成报告失败:', error);
    ElMessage.error('生成报告失败: ' + (error?.response?.data?.detail || error?.message || error));
  } finally {
    isGeneratingReport.value = false;
  }
};

// 下载报告（PDF 格式）
const downloadReport = async () => {
  if (!generatedReport.value) return;

  try {
    await reportAPI.downloadReportPDF(generatedReport.value, reportTitle.value, reportFigures.value);
    ElMessage.success('报告下载成功');
  } catch (error: any) {
    console.error('下载报告失败:', error);
    ElMessage.error('下载报告失败: ' + (error?.response?.data?.detail || error?.message || error));
  }
};

// 查看选中的模板
const viewSelectedTemplate = () => {
  const template = reportTemplates.value.find(t => t.id === selectedTemplateId.value);
  if (template) {
    viewingTemplate.value = template;
  } else if (selectedTemplateId.value === 'default') {
    const defaultTemplate = reportTemplates.value.find(t => t.is_default);
    if (defaultTemplate) {
      viewingTemplate.value = defaultTemplate;
    } else {
      viewingTemplate.value = {
        id: 'default$placeholder',
        name: '默认分析报告模板',
        description: '系统内置的标准数据分析报告模板',
        content: '正在加载默认模板内容...',
        is_default: true,
        created_at: new Date().toISOString(),
      };
    }
  }
};

// 查看指定模板
const viewTemplate = (template: ReportTemplate) => {
  viewingTemplate.value = template;
};

// 删除模板
const deleteTemplate = async (templateId: string) => {
  try {
    await ElMessageBox.confirm('确定要删除这个模板吗？', '删除确认', {
      type: 'warning'
    });

    await reportAPI.deleteTemplate(templateId);
    ElMessage.success('模板删除成功');
    await loadReportTemplates();
  } catch (error: unknown) {
    if (error !== 'cancel') {
      console.error('删除模板失败:', error);
      ElMessage.error('删除模板失败');
    }
  }
};
</script>

<template>
  <el-dialog v-model="visible" title="生成分析报告" width="80%" :close-on-click-modal="false" :close-on-press-escape="false">
    <el-tabs v-model="activeTab">
      <!-- 生成报告选项卡 -->
      <el-tab-pane label="生成报告" name="generate">
        <div class="report-generation-options">
          <div class="template-selection">
            <el-select v-model="selectedTemplateId" placeholder="选择报告模板" style="width: 300px;">
              <el-option label="默认模板" value="default"></el-option>
              <el-option v-for="template in reportTemplates.filter(t => !t.is_default)" :key="template.id"
                :label="template.name" :value="template.id"></el-option>
            </el-select>
            <el-button @click="viewSelectedTemplate" :disabled="!selectedTemplateId">
              查看模板
            </el-button>
            <el-button type="primary" :loading="isGeneratingReport" @click="generateReport">
              生成报告
            </el-button>
          </div>
        </div>

        <!-- 模板预览 -->
        <div v-if="viewingTemplate" class="template-preview">
          <h4>{{ viewingTemplate.name }}</h4>
          <p>{{ viewingTemplate.description }}</p>
          <div class="template-content">
            <pre>{{ viewingTemplate.content }}</pre>
          </div>
        </div>
      </el-tab-pane>

      <!-- 模板管理选项卡 -->
      <el-tab-pane label="模板管理" name="manage">
        <div class="template-management">
          <div class="management-actions">
            <el-button type="primary" @click="uploadTemplateDialogVisible = true">
              <el-icon>
                <Upload />
              </el-icon>
              上传新模板
            </el-button>
          </div>

          <el-table :data="reportTemplates" style="width: 100%; margin-top: 16px;">
            <el-table-column prop="name" label="模板名称" width="200"></el-table-column>
            <el-table-column prop="description" label="描述"></el-table-column>
            <el-table-column label="类型" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.is_default ? 'info' : 'success'">
                  {{ scope.row.is_default ? '系统' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="scope">
                <el-button type="text" @click="viewTemplate(scope.row)">查看</el-button>
                <el-button v-if="!scope.row.is_default" type="text" @click="deleteTemplate(scope.row.id)"
                  style="color: #f56c6c;">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <div v-if="generatedReport" class="report-preview-section">
      <h3>报告预览</h3>
      <div class="markdown-content">
        <div style="white-space: pre-wrap; font-family: inherit;" v-html="formattedReport"></div>
      </div>
    </div>

    <div v-if="reportFigures.length > 0" class="report-figures-section">
      <h3>报告图表</h3>
      <div v-for="(figure, index) in reportFigures" :key="index">
        <img :src="`data:image/png;base64,${figure}`" alt="报告图表"
          style="max-width: 100%; height: auto; margin-bottom: 10px;">
      </div>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visible = false">关闭</el-button>
        <el-button type="primary" @click="downloadReport" :disabled="!generatedReport">
          <el-icon>
            <Download />
          </el-icon>
          下载报告
        </el-button>
      </span>
    </template>

    <!-- 模板上传对话框 -->
    <TemplateUploadDialog v-model:visible="uploadTemplateDialogVisible" @template-uploaded="loadReportTemplates" />
  </el-dialog>
</template>

<style lang="scss" scoped>
/* 报告生成相关样式 */
.report-generation-options {
  margin-bottom: 24px;

  .template-selection {
    display: flex;
    gap: 16px;
    align-items: center;
    margin-bottom: 16px;
  }

}

.template-preview {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;

  h4 {
    margin: 0 0 8px 0;
    color: #374151;
    font-weight: 600;
  }

  p {
    margin: 0 0 16px 0;
    color: #6b7280;
    font-size: 14px;
  }

  .template-content {
    max-height: 300px;
    overflow-y: auto;

    pre {
      background: #f3f4f6;
      padding: 12px;
      border-radius: 6px;
      font-size: 12px;
      line-height: 1.5;
      margin: 0;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
  }

}

.template-management {
  .management-actions {
    margin-bottom: 16px;
  }
}

.report-preview-section {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;

  h3 {
    margin: 0 0 16px 0;
    color: #374151;
  }
}

.report-figures-section {
  margin-top: 24px;

  h3 {
    margin: 0 0 16px 0;
    color: #374151;
  }
}

/* 覆盖一些 GitHub 样式 */
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
