<script setup lang="ts">
import type { CleaningAction, CleaningSuggestion, DataQualityReport } from '@/utils/api'
import {
  ArrowDown, ArrowRight, Back, CircleCheck, CircleClose, Connection, DataAnalysis,
  Document,
  DocumentChecked, DocumentCopy, Edit, EditPen, Grid, InfoFilled, QuestionFilled,
  RefreshRight,
  Upload,
  Warning
} from '@element-plus/icons-vue'
import { computed, ref } from 'vue'

// 使用 defineModel 实现对话框可见性双向绑定
const visible = defineModel<boolean>('visible', { required: true })

// 定义步骤类型
type CleaningStep = 'upload' | 'analysis' | 'cleaning' | 'complete'

// 当前清洗步骤
const step = defineModel<CleaningStep>('step', {
  required: true,
  default: 'upload'
})

// 用户要求和模型选择的双向绑定
const userRequirements = defineModel<string>('userRequirements', { default: '' })
const selectedModel = defineModel<string>('selectedModel', { default: '' })
const fileMetadata = defineModel<{ name: string, description: string }>('fileMetadata', { required: true })

// 定义组件属性
interface Props {
  file: File | null
  dataQualityReport: DataQualityReport | null
  cleaningSuggestions: CleaningSuggestion[]
  fieldMappings: Record<string, string>
  isAnalyzing: boolean
  isCleaning: boolean
  selectedCleaningActions: CleaningAction[]
  analysisResult: any
  availableModels: Array<{ value: string, label: string }>
}

const props = withDefaults(defineProps<Props>(), {
  dataQualityReport: null,
  cleaningSuggestions: () => [],
  fieldMappings: () => ({}),
  isAnalyzing: false,
  isCleaning: false,
  selectedCleaningActions: () => [],
  analysisResult: null,
  availableModels: () => []
})

// 定义组件事件
const emit = defineEmits<{
  analyze: []
  skipAndUpload: []
  applyCleaningActions: []
  complete: []
  close: []
  toggleCleaningAction: [suggestion: CleaningSuggestion]
}>()

// 智能分析相关
const showAdvancedOptions = ref(false)

const dialogWidth = computed(() => {
  // 根据不同步骤返回不同宽度
  switch (step.value) {
    case 'upload':
      return '600px'
    case 'analysis':
      return '55%'
    case 'cleaning':
      return '70%'
    case 'complete':
      return '700px'
    default:
      return '60%'
  }
})

// 获取质量评分的颜色
const getQualityScoreColor = (score: number) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

// 获取质量评分的文本
const getQualityScoreText = (score: number) => {
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 60) return '一般'
  return '需要改进'
}

// 获取问题类型的图标
const getIssueTypeIcon = (type: string) => {
  switch (type) {
    case 'missing_values':
      return QuestionFilled
    case 'outliers':
      return Warning
    case 'duplicates':
    case 'duplicate_rows':
      return DocumentCopy
    case 'invalid_values':
      return CircleClose
    case 'column_name':
      return Edit
    case 'data_type':
      return DocumentChecked
    default:
      return InfoFilled
  }
}

// 获取问题类型的颜色
const getIssueTypeColor = (type: string) => {
  switch (type) {
    case 'missing_values':
      return 'warning'
    case 'outliers':
      return 'danger'
    case 'duplicates':
    case 'duplicate_rows':
      return 'info'
    case 'invalid_values':
      return 'danger'
    case 'column_name':
      return 'primary'
    case 'data_type':
      return 'success'
    default:
      return 'info'
  }
}

// 获取优先级颜色
const getPriorityColor = (priority: string) => {
  switch (priority) {
    case 'high':
      return 'danger'
    case 'medium':
      return 'warning'
    case 'low':
      return 'success'
    default:
      return 'info'
  }
}

// 检查清洗动作是否已选择
const isCleaningActionSelected = (suggestion: CleaningSuggestion) => {
  return props.selectedCleaningActions.some(a =>
    a.type === suggestion.type && a.column === suggestion.column
  )
}

// 切换清洗动作选择
const toggleCleaningAction = (suggestion: CleaningSuggestion) => {
  emit('toggleCleaningAction', suggestion)
}

// 开始智能分析
const startAnalysis = () => {
  emit('analyze')
}

// 跳过分析直接上传
const skipAnalysisAndUpload = () => {
  emit('skipAndUpload')
}

// 应用清洗操作
const applyCleaningActions = () => {
  emit('applyCleaningActions')
}

// 完成清洗
const completeCleaningAndUpload = () => {
  emit('complete')
}

// 关闭对话框
const closeDialog = () => {
  emit('close')
}
</script>

<template>
  <el-dialog v-model="visible" title="数据清洗与分析" :width="dialogWidth" :before-close="closeDialog">
    <div class="cleaning-content">
      <!-- 步骤指示器 -->
      <div class="cleaning-steps">
        <div class="step" v-for="stepItem in [
          { key: 'upload', name: '文件上传' },
          { key: 'analysis', name: '智能分析' },
          { key: 'cleaning', name: '清洗建议' },
          { key: 'complete', name: '完成上传' }
        ]" :key="stepItem.key" :class="{ active: step === stepItem.key }">
          <div class="step-icon">
            <el-icon>
              <template v-if="step !== 'upload' && step !== stepItem.key">
                <Check />
              </template>
              <template v-else-if="step === stepItem.key">
                <CircleCheck />
              </template>
              <template v-else>
                <CircleClose />
              </template>
            </el-icon>
          </div>
          <div class="step-title">{{ stepItem.name }}</div>
        </div>
      </div>

      <!-- 上传文件信息 -->
      <div v-if="step === 'upload'" class="upload-info">
        <div class="file-details">
          <div class="file-icon">
            <el-icon size="48" color="#667eea">
              <Document />
            </el-icon>
          </div>
          <div class="file-meta">
            <div class="file-name">{{ fileMetadata.name }}</div>
            <div class="file-size">{{ file ? (file.size / 1024 / 1024).toFixed(2) : 0 }} MB</div>
            <div class="file-type">{{ file?.name.split('.').pop()?.toUpperCase() }} 文件</div>
          </div>
        </div>

        <!-- 文件元数据编辑 -->
        <div class="file-metadata">
          <el-form label-width="80px" label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="文件名称">
                  <el-input v-model="fileMetadata.name" placeholder="请输入文件名称" :prefix-icon="Document" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="文件描述">
                  <el-input v-model="fileMetadata.description" placeholder="请输入文件描述信息" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>

        <!-- 智能分析选项 -->
        <div class="smart-analysis-options">
          <div class="options-header">
            <h4>智能分析选项</h4>
            <el-button type="text" @click="showAdvancedOptions = !showAdvancedOptions">
              {{ showAdvancedOptions ? '收起高级选项' : '展开高级选项' }}
              <el-icon>
                <ArrowRight v-if="!showAdvancedOptions" />
                <ArrowDown v-else />
              </el-icon>
            </el-button>
          </div>

          <div class="basic-options">
            <el-form-item label="自定义清洗要求">
              <el-input v-model="userRequirements" type="textarea"
                placeholder="例如：请重点关注数据标准化，确保所有列名都符合命名规范，处理缺失值，并验证邮箱格式..." :rows="3" show-word-limit maxlength="500" />
              <div class="hint-text">
                <el-icon>
                  <InfoFilled />
                </el-icon>
                描述您的具体清洗需求，AI将根据您的要求生成个性化的清洗建议
              </div>
            </el-form-item>
          </div>

          <el-collapse-transition>
            <div v-show="showAdvancedOptions" class="advanced-options">
              <el-form-item label="选择AI模型">
                <el-select v-model="selectedModel" placeholder="请选择AI模型">
                  <el-option v-for="model in availableModels" :key="model.value" :label="model.label"
                    :value="model.value" />
                </el-select>
                <div class="hint-text">
                  <el-icon>
                    <InfoFilled />
                  </el-icon>
                  不同模型在字段理解和建议生成方面各有特色
                </div>
              </el-form-item>
            </div>
          </el-collapse-transition>
        </div>

        <div class="file-actions">
          <el-button @click="closeDialog" size="large">
            取消
          </el-button>
          <el-button type="primary" @click="skipAnalysisAndUpload" size="large">
            <el-icon>
              <Upload />
            </el-icon>
            跳过分析，直接上传
          </el-button>
          <el-button type="success" @click="startAnalysis" :loading="isAnalyzing" size="large">
            <el-icon>
              <DataAnalysis />
            </el-icon>
            开始智能分析
          </el-button>
        </div>
      </div>

      <!-- 数据质量分析结果 -->
      <div v-if="step === 'analysis'" class="analysis-results">
        <div v-if="isAnalyzing" class="loading-status">
          <el-empty description="正在智能分析数据质量，请稍候...">
            <template #image>
              <el-icon size="60" color="#667eea">
                <DataAnalysis />
              </el-icon>
            </template>
          </el-empty>
        </div>
        <div v-else>
          <!-- 智能分析结果总览 -->
          <div class="smart-analysis-summary">
            <div class="summary-header">
              <div></div> <!-- 空占位符 -->
              <el-tag :type="getQualityScoreColor(analysisResult?.quality_report?.overall_score || 0)" size="large">
                {{ analysisResult?.quality_report?.overall_score || 0 }}分 -
                {{ getQualityScoreText(analysisResult?.quality_report?.overall_score || 0) }}
              </el-tag>
            </div>

            <el-row :gutter="16" class="summary-cards">
              <el-col :span="6">
                <div class="summary-card">
                  <div class="card-icon data-icon">
                    <el-icon>
                      <Document />
                    </el-icon>
                  </div>
                  <div class="card-content">
                    <div class="card-number">{{ dataQualityReport?.total_rows || 0 }}</div>
                    <div class="card-label">数据行数</div>
                  </div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="summary-card">
                  <div class="card-icon columns-icon">
                    <el-icon>
                      <Grid />
                    </el-icon>
                  </div>
                  <div class="card-content">
                    <div class="card-number">{{ dataQualityReport?.total_columns || 0 }}</div>
                    <div class="card-label">数据列数</div>
                  </div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="summary-card">
                  <div class="card-icon issues-icon">
                    <el-icon>
                      <Warning />
                    </el-icon>
                  </div>
                  <div class="card-content">
                    <div class="card-number">{{ cleaningSuggestions.length }}</div>
                    <div class="card-label">发现问题</div>
                  </div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="summary-card">
                  <div class="card-icon mapping-icon">
                    <el-icon>
                      <Connection />
                    </el-icon>
                  </div>
                  <div class="card-content">
                    <div class="card-number">{{ Object.keys(fieldMappings).length }}</div>
                    <div class="card-label">字段映射</div>
                  </div>
                </div>
              </el-col>
            </el-row>
          </div>

          <!-- 字段映射结果 -->
          <div v-if="Object.keys(fieldMappings).length > 0" class="field-mappings-section">
            <div class="section-header">
              <h4>字段理解与映射建议</h4>
              <el-tag type="info">{{ Object.keys(fieldMappings).length }} 个字段</el-tag>
            </div>

            <div class="mappings-grid">
              <div v-for="(suggestion, originalName) in fieldMappings" :key="originalName" class="mapping-card">
                <div class="mapping-header">
                  <div class="original-field">
                    <el-tag type="info" size="small">原始字段</el-tag>
                    <span class="field-name" :title="originalName">{{ originalName }}</span>
                  </div>
                  <div class="mapping-arrow">
                    <el-icon class="arrow-icon">
                      <ArrowRight />
                    </el-icon>
                  </div>
                  <div class="suggested-field">
                    <el-tag type="success" size="small">标准字段</el-tag>
                    <span class="field-name" :title="suggestion">{{ suggestion }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 详细数据质量报告 -->
          <div class="detailed-quality-report">
            <div class="section-header">
              <h4>详细质量报告</h4>
              <el-button type="text" @click="showAdvancedOptions = !showAdvancedOptions">
                {{ showAdvancedOptions ? '收起详情' : '查看详情' }}
              </el-button>
            </div>

            <el-collapse-transition>
              <div v-show="showAdvancedOptions" class="report-details">
                <el-descriptions :column="2" border>
                  <el-descriptions-item v-for="(value, key) in dataQualityReport" :key="key" :label="key">
                    <span v-if="typeof value === 'number'">{{ value.toFixed(2) }}</span>
                    <span v-else-if="typeof value === 'boolean'">{{ value ? '是' : '否' }}</span>
                    <span v-else>{{ value }}</span>
                  </el-descriptions-item>
                </el-descriptions>
              </div>
            </el-collapse-transition>
          </div>

          <!-- 分析结果操作区域 -->
          <div class="analysis-actions">
            <div class="action-info">
              <el-alert :title="analysisResult?.summary || '分析完成'"
                :type="cleaningSuggestions.length > 0 ? 'warning' : 'success'" :description="cleaningSuggestions.length > 0 ?
                  `发现 ${cleaningSuggestions.length} 个可优化的问题，建议查看清洗建议以提升数据质量。` :
                  '您的数据质量良好，可以直接上传。'" show-icon :closable="false" />
            </div>

            <div class="action-buttons">
              <el-button type="primary" @click="step = 'cleaning'" :disabled="cleaningSuggestions.length === 0"
                size="large">
                <el-icon>
                  <ArrowRight />
                </el-icon>
                下一步：执行清洗操作 ({{ cleaningSuggestions.length }})
              </el-button>

              <el-button type="success" @click="skipAnalysisAndUpload" size="large" :disabled="!dataQualityReport">
                <el-icon>
                  <Upload />
                </el-icon>
                {{ cleaningSuggestions.length === 0 ? '直接上传数据' : '忽略问题，仅应用字段映射并上传' }}
              </el-button>

              <el-button @click="step = 'upload'" size="large">
                <el-icon>
                  <Back />
                </el-icon>
                返回上传
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 清洗建议选择 -->
      <div v-if="step === 'cleaning'" class="cleaning-suggestions">
        <div v-if="isCleaning" class="cleaning-progress">
          <el-empty description="正在记录您的清洗选择，请稍候..." />
        </div>
        <div v-else>
          <div class="suggestions-header">
            <div class="header-content">
              <div class="title">选择数据清洗建议</div>
              <div class="subtitle">
                根据数据质量分析结果，我们为您提供了以下清洗建议。请选择您认为合适的建议，系统将自动执行这些清洗操作。
              </div>
            </div>

            <el-alert title="功能说明" description="本系统将根据您选择的建议自动执行数据清洗操作，包括字段重命名、缺失值处理、异常值处理等，清洗后的数据将保存到Dremio中。"
              type="info" show-icon :closable="false" />
          </div>

          <div class="suggestions-actions">
            <div class="action-info">
              已选择 {{ selectedCleaningActions.length }} 个建议，共 {{ cleaningSuggestions.length }} 个建议
            </div>
            <div class="action-buttons">
              <el-button type="primary" @click="applyCleaningActions" :loading="isCleaning"
                :disabled="selectedCleaningActions.length === 0" size="large">
                <el-icon>
                  <DocumentChecked />
                </el-icon>
                执行选中的清洗操作 ({{ selectedCleaningActions.length }})
              </el-button>

              <el-button @click="skipAnalysisAndUpload" size="large">
                <el-icon>
                  <Upload />
                </el-icon>
                跳过清洗直接上传
              </el-button>

              <el-button @click="step = 'analysis'" size="large">
                <el-icon>
                  <Back />
                </el-icon>
                返回分析结果
              </el-button>
            </div>
          </div>

          <div class="suggestions-list">
            <div class="suggestion-item" v-for="(suggestion, index) in cleaningSuggestions" :key="index">
              <div class="item-checkbox">
                <el-checkbox :checked="isCleaningActionSelected(suggestion)" @change="toggleCleaningAction(suggestion)"
                  size="large" />
              </div>
              <div class="item-icon" :class="`icon-${getIssueTypeColor(suggestion.type)}`">
                <el-icon :component="getIssueTypeIcon(suggestion.type)" />
              </div>
              <div class="item-content">
                <div class="item-header">
                  <div class="item-title">{{ suggestion.description }}</div>
                  <div class="item-badges">
                    <el-tag :type="getIssueTypeColor(suggestion.type)" size="small">
                      {{ suggestion.type }}
                    </el-tag>
                    <el-tag :type="getPriorityColor(suggestion.priority || 'medium')" size="small">
                      {{ suggestion.priority || 'medium' }} 优先级
                    </el-tag>
                  </div>
                </div>
                <div class="item-details">
                  <div class="detail-row">
                    <span class="detail-label">影响列:</span>
                    <el-tag type="info" size="small">{{ suggestion.column }}</el-tag>
                  </div>
                  <div class="detail-row" v-if="suggestion.impact">
                    <span class="detail-label">影响程度:</span>
                    <span class="detail-value">{{ suggestion.impact }}</span>
                  </div>
                  <div class="detail-row" v-if="suggestion.reason">
                    <span class="detail-label">建议原因:</span>
                    <span class="detail-value">{{ suggestion.reason }}</span>
                  </div>
                </div>
              </div>
              <div class="item-action">
                <el-button :type="isCleaningActionSelected(suggestion) ? 'success' : 'default'" size="small"
                  @click="toggleCleaningAction(suggestion)">
                  {{ isCleaningActionSelected(suggestion) ? '已选择' : '选择' }}
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 完成状态 -->
      <div v-if="step === 'complete'" class="complete-status">
        <el-result status="success" title="处理完成" :sub-title="analysisResult?.data_uploaded ?
          '数据已成功上传到Dremio，您可以在数据源列表中查看' :
          '数据处理完成，请选择操作'">
          <template #extra>
            <div class="complete-actions">
              <el-button type="primary" @click="completeCleaningAndUpload" size="large"
                v-if="analysisResult?.data_uploaded">
                <el-icon>
                  <CircleCheck />
                </el-icon>
                关闭并查看数据源列表
              </el-button>

              <el-button type="primary" @click="skipAnalysisAndUpload" size="large"
                v-if="!analysisResult?.data_uploaded">
                <el-icon>
                  <Upload />
                </el-icon>
                立即上传数据
              </el-button>

              <el-button @click="startAnalysis" size="large">
                <el-icon>
                  <RefreshRight />
                </el-icon>
                重新分析数据质量
              </el-button>

              <el-button @click="step = 'cleaning'"
                v-if="cleaningSuggestions.length > 0 && !analysisResult?.data_uploaded" size="large">
                <el-icon>
                  <EditPen />
                </el-icon>
                重新选择清洗操作
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
      </div>
    </div>
  </el-dialog>
</template>

<style lang="scss" scoped>
.cleaning-content {
  padding: 20px;

  .cleaning-steps {
    display: flex;
    justify-content: space-between;
    margin-bottom: 32px;
    position: relative;

    &::before {
      content: '';
      position: absolute;
      top: 20px;
      left: 20px;
      right: 20px;
      height: 2px;
      background: #e5e7eb;
      z-index: 1;
    }

    .step {
      display: flex;
      flex-direction: column;
      align-items: center;
      position: relative;
      flex: 1;
      z-index: 2;

      .step-icon {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #f3f4f6;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 8px;
        transition: all 0.3s ease;

        .el-icon {
          font-size: 20px;
          color: #9ca3af;
        }
      }

      .step-title {
        font-size: 12px;
        color: #6b7280;
        text-align: center;
        font-weight: 500;
      }

      &.active {
        .step-icon {
          background: #3b82f6;

          .el-icon {
            color: white;
          }
        }

        .step-title {
          color: #3b82f6;
          font-weight: 600;
        }
      }
    }
  }

  .upload-info {
    .file-details {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 24px;
      padding: 16px;
      background: white;
      border-radius: 8px;
      border: 1px solid #e5e7eb;

      .file-icon {
        flex-shrink: 0;
      }

      .file-meta {
        flex: 1;

        .file-name {
          font-size: 18px;
          font-weight: 600;
          color: #1f2937;
          margin-bottom: 4px;
        }

        .file-size {
          font-size: 14px;
          color: #6b7280;
          margin-bottom: 2px;
        }

        .file-type {
          font-size: 12px;
          color: #9ca3af;
        }
      }
    }
  }

  .smart-analysis-options {
    margin-bottom: 24px;
    padding: 20px;
    background: white;
    border-radius: 8px;
    border: 1px solid #e5e7eb;

    .options-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;

      h4 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: #1f2937;
      }
    }

    .basic-options {
      margin-bottom: 16px;

      .hint-text {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: #6b7280;
        margin-top: 4px;
      }
    }

    .advanced-options {
      .hint-text {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: #6b7280;
        margin-top: 4px;
      }
    }
  }

  .file-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 24px;

    .el-button {
      padding: 12px 24px;
      border-radius: 8px;
      font-weight: 500;
    }
  }

  .analysis-results {
    .loading-status {
      padding: 40px 0;
      text-align: center;
    }

    // 智能分析结果样式
    .smart-analysis-summary {
      margin-bottom: 24px;

      .summary-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
      }

      .summary-cards {
        .summary-card {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px;
          background: white;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
          transition: all 0.2s ease;

          &:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
          }

          .card-icon {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;

            &.data-icon {
              background: #eff6ff;
              color: #3b82f6;
            }

            &.columns-icon {
              background: #f0fdf4;
              color: #22c55e;
            }

            &.issues-icon {
              background: #fef3c7;
              color: #f59e0b;
            }

            &.mapping-icon {
              background: #fce7f3;
              color: #ec4899;
            }
          }

          .card-content {
            .card-number {
              font-size: 24px;
              font-weight: 700;
              color: #1f2937;
              line-height: 1;
            }

            .card-label {
              font-size: 12px;
              color: #6b7280;
              margin-top: 4px;
            }
          }
        }
      }
    }

    // 字段映射样式
    .field-mappings-section {
      margin-bottom: 24px;

      .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;

        h4 {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
          color: #1f2937;
        }
      }

      .mappings-grid {
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-height: 300px;
        overflow-y: auto;
        padding-right: 8px;

        .mapping-card {
          padding: 16px;
          background: white;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
          transition: all 0.2s ease;

          &:hover {
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border-color: #d1d5db;
          }

          .mapping-header {
            display: flex;
            align-items: center;

            .original-field,
            .suggested-field {
              display: flex;
              align-items: center;
              gap: 8px;
              flex: 1;

              .field-name {
                font-weight: 500;
                color: #374151;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                max-width: 200px;
              }
            }

            .mapping-arrow {
              display: flex;
              align-items: center;
              justify-content: center;
              width: 40px;
              flex-shrink: 0;

              .arrow-icon {
                color: #6366f1;
                font-size: 20px;
              }
            }
          }
        }
      }
    }

    // 详细报告样式
    .detailed-quality-report {
      margin-bottom: 24px;

      .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;

        h4 {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
          color: #1f2937;
        }
      }

      .report-details {
        background: white;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
      }
    }

    .analysis-actions {
      margin-top: 24px;

      .action-info {
        margin-bottom: 16px;
      }

      .action-buttons {
        display: flex;
        gap: 12px;
        justify-content: center;
        margin-top: 24px;

        .el-button {
          padding: 12px 24px;
          border-radius: 8px;
          font-weight: 500;
        }
      }
    }
  }

  .cleaning-suggestions {
    .suggestions-header {
      margin-bottom: 24px;

      .header-content {
        margin-bottom: 16px;

        .title {
          font-size: 18px;
          font-weight: 600;
          color: #1f2937;
          margin-bottom: 8px;
        }

        .subtitle {
          font-size: 14px;
          color: #6b7280;
        }
      }
    }

    .suggestions-actions {
      background: #f9fafb;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 24px;
      border: 1px solid #e5e7eb;

      .action-info {
        font-size: 14px;
        color: #6b7280;
        margin-bottom: 12px;
        text-align: center;
      }

      .action-buttons {
        display: flex;
        gap: 12px;
        justify-content: center;
        flex-wrap: wrap;

        .el-button {
          border-radius: 8px;
          padding: 10px 20px;
          font-weight: 500;
        }
      }
    }

    .suggestions-list {
      .suggestion-item {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        padding: 20px;
        background: white;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        margin-bottom: 16px;
        transition: all 0.2s ease;

        &:hover {
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        .item-checkbox {
          margin-top: 4px;
        }

        .item-icon {
          width: 40px;
          height: 40px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          margin-top: 4px;

          &.icon-success {
            background: #f0fdf4;
            color: #22c55e;
          }

          &.icon-warning {
            background: #fef3c7;
            color: #f59e0b;
          }

          &.icon-danger {
            background: #fef2f2;
            color: #ef4444;
          }

          &.icon-info {
            background: #eff6ff;
            color: #3b82f6;
          }

          &.icon-primary {
            background: #f3f4f6;
            color: #6366f1;
          }
        }

        .item-content {
          flex: 1;

          .item-header {
            margin-bottom: 12px;

            .item-title {
              font-size: 16px;
              font-weight: 600;
              color: #1f2937;
              margin-bottom: 8px;
            }

            .item-badges {
              display: flex;
              gap: 8px;
            }
          }

          .item-details {
            .detail-row {
              display: flex;
              align-items: center;
              gap: 8px;
              margin-bottom: 8px;

              &:last-child {
                margin-bottom: 0;
              }

              .detail-label {
                font-size: 14px;
                color: #6b7280;
                font-weight: 500;
                min-width: 80px;
              }

              .detail-value {
                font-size: 14px;
                color: #374151;
              }
            }
          }
        }

        .item-action {
          margin-top: 4px;
        }
      }
    }
  }

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
}

.file-metadata {
  margin: 16px 0;
  padding: 16px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e5e7eb;

  .el-form-item {
    margin-bottom: 16px;

    :deep(.el-form-item__label) {
      font-weight: 500;
      color: #374151;
    }

    :deep(.el-input__wrapper) {
      border-radius: 6px;
      transition: all 0.3s ease;

      &.is-focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
      }
    }

    :deep(.el-textarea__inner) {
      border-radius: 6px;
      transition: all 0.3s ease;

      &:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
      }
    }
  }
}

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
    padding: 0;
  }
}

// 响应式设计
@media (max-width: 768px) {
  .cleaning-content {
    .cleaning-steps {
      flex-wrap: wrap;
      gap: 12px;

      &::before {
        display: none;
      }

      .step {
        flex-basis: calc(50% - 6px);
        margin-bottom: 12px;
      }
    }

    .upload-info {
      .file-details {
        margin-bottom: 12px;

        .file-name {
          font-size: 16px;
        }

        .file-size {
          font-size: 12px;
        }
      }

      .file-actions {
        flex-direction: column;
        gap: 8px;

        .el-button {
          width: 100%;
          padding: 10px;
          font-size: 14px;
        }
      }
    }

    .smart-analysis-summary {
      .summary-cards {
        .el-col {
          width: 50%;
          margin-bottom: 12px;
        }
      }
    }
  }
}
</style>
