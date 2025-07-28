<script setup lang="ts">
import type { AnalyzeDataQualityState, CleaningSuggestion, DataQualityReport } from '@/types/cleaning';
import { ArrowRight, Back, DataAnalysis, Upload } from '@element-plus/icons-vue';
import { ElAlert, ElButton, ElEmpty, ElIcon } from 'element-plus';
import DataQualityReportDetail from './DataQualityReport.vue';
import FieldMappingsGrid from './FieldMappingsGrid.vue';
import QualitySummaryCards from './QualitySummaryCards.vue';

// 定义组件属性
defineProps<{
  dataQualityReport: DataQualityReport | null;
  cleaningSuggestions: CleaningSuggestion[];
  fieldMappings: Record<string, string>;
  isAnalyzing: boolean;
  analysisResult: AnalyzeDataQualityState | null;
}>();

// 定义组件事件
const emit = defineEmits<{
  skipAndUpload: [];
  gotoCleaning: [];
  gotoUpload: [];
}>();
</script>

<template>
  <div class="analysis-results">
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
      <QualitySummaryCards :data-quality-report="dataQualityReport"
        :cleaning-suggestions-count="cleaningSuggestions.length"
        :field-mappings-count="Object.keys(fieldMappings).length"
        :overall-score="analysisResult?.quality_report.overall_score || 0" />

      <!-- 字段映射结果 -->
      <FieldMappingsGrid :field-mappings="fieldMappings" />

      <!-- 详细数据质量报告 -->
      <DataQualityReportDetail :data-quality-report="dataQualityReport" />

      <!-- 分析结果操作区域 -->
      <div class="analysis-actions">
        <div class="action-info">
          <el-alert :title="analysisResult?.summary || '分析完成'"
            :type="cleaningSuggestions.length > 0 ? 'warning' : 'success'" :description="cleaningSuggestions.length > 0 ?
              `发现 ${cleaningSuggestions.length} 个可优化的问题，建议查看清洗建议以提升数据质量。` :
              '您的数据质量良好，可以直接上传。'" show-icon :closable="false" />
        </div>

        <div class="action-buttons">
          <el-button type="primary" @click="emit('gotoCleaning')" :disabled="cleaningSuggestions.length === 0"
            size="large">
            <el-icon>
              <ArrowRight />
            </el-icon>
            下一步：执行清洗操作 ({{ cleaningSuggestions.length }})
          </el-button>

          <el-button type="success" @click="emit('skipAndUpload')" size="large" :disabled="!dataQualityReport">
            <el-icon>
              <Upload />
            </el-icon>
            {{ cleaningSuggestions.length === 0 ? '直接上传数据' : '忽略问题，仅应用字段映射并上传' }}
          </el-button>

          <el-button @click="emit('gotoUpload')" size="large">
            <el-icon>
              <Back />
            </el-icon>
            返回上传
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.analysis-results {
  .loading-status {
    padding: 40px 0;
    text-align: center;
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
</style>
