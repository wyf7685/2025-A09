<script setup lang="ts">
import type { DataQualityReport } from '@/types/cleaning';
import { Connection, Document, Grid, Warning } from '@element-plus/icons-vue';

// 定义组件属性
defineProps<{
  dataQualityReport: DataQualityReport | null
  cleaningSuggestionsCount: number
  fieldMappingsCount: number
  overallScore?: number
}
>()

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
</script>

<template>
  <div class="smart-analysis-summary">
    <div class="summary-header">
      <div></div> <!-- 空占位符 -->
      <el-tag :type="getQualityScoreColor(overallScore || 0)" size="large">
        {{ overallScore || 0 }}分 -
        {{ getQualityScoreText(overallScore || 0) }}
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
            <div class="card-number">{{ cleaningSuggestionsCount }}</div>
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
            <div class="card-number">{{ fieldMappingsCount }}</div>
            <div class="card-label">字段映射</div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style lang="scss" scoped>
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

// 响应式设计
@media (max-width: 768px) {
  .smart-analysis-summary {
    .summary-cards {
      .el-col {
        width: 50%;
        margin-bottom: 12px;
      }
    }
  }
}
</style>
