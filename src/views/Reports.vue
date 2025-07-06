<script setup lang="ts">
import { marked } from 'marked';
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAppStore } from '@/stores/app';
import type { AnalysisReport, Figure } from '@/types';

const router = useRouter()
const appStore = useAppStore()

// 响应式数据
const loading = ref<boolean>(false)
const reports = ref<AnalysisReport[]>([])
const showReportDialog = ref<boolean>(false)
const selectedReport = ref<AnalysisReport | null>(null)

// 方法
const refreshReports = async (): Promise<void> => {
  loading.value = true
  try {
    const session = appStore.currentSession
    if (session && session.analysis_results) {
      reports.value = session.analysis_results as AnalysisReport[]
    }
  } catch (error) {
    console.error('刷新报告失败:', error)
  } finally {
    loading.value = false
  }
}

const formatReportTitle = (report: AnalysisReport): string => {
  const date = new Date(report.timestamp)
  return `数据分析报告 - ${date.toLocaleDateString()}`
}

const formatDate = (timestamp: string): string => {
  const date = new Date(timestamp)
  return date.toLocaleString()
}

const getReportSummary = (report: string | undefined): string => {
  if (!report) return ''
  const lines = report.split('\n').filter(line => line.trim())
  return lines.slice(0, 2).join(' ').substring(0, 150) + '...'
}

const formatMarkdown = async (content: string | undefined): Promise<string> => {
  return await marked(content || '')
}

const viewReport = (report: AnalysisReport): void => {
  selectedReport.value = report
  showReportDialog.value = true
}

const exportReport = async (report: AnalysisReport): Promise<void> => {
  try {
    const response = await appStore.exportReport('markdown')
    const blob = new Blob([response], { type: 'text/markdown' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analysis_report_${new Date(report.timestamp).toISOString().split('T')[0]}.md`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('导出报告失败:', error)
  }
}

onMounted(() => {
  refreshReports()
})
</script>

<template>
  <div class="reports-page">
    <div class="page-header">
      <div class="header-content">
        <h1>分析报告</h1>
        <p class="header-subtitle">查看和管理您的数据分析报告</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshReports" :loading="loading">
          <el-icon>
            <Refresh />
          </el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div class="reports-content">
      <!-- 空状态 -->
      <div v-if="!loading && reports.length === 0" class="empty-state">
        <el-empty description="暂无分析报告" :image-size="120">
          <template #description>
            <p>还没有生成任何分析报告</p>
            <p class="empty-tip">上传数据并使用自动分析功能来生成报告</p>
          </template>
          <el-button type="primary" @click="$router.push('/auto-analysis')">
            开始分析
          </el-button>
        </el-empty>
      </div>

      <!-- 报告列表 -->
      <div v-else-if="!loading" class="reports-list">
        <el-card v-for="report in reports" :key="report.timestamp" class="report-card" shadow="hover">
          <div class="report-header">
            <div class="report-info">
              <h3>{{ formatReportTitle(report) }}</h3>
              <div class="report-meta">
                <span class="meta-item">
                  <el-icon>
                    <Calendar />
                  </el-icon>
                  {{ formatDate(report.timestamp) }}
                </span>
                <span class="meta-item">
                  <el-icon>
                    <DataAnalysis />
                  </el-icon>
                  数据量: {{ report.dataset_shape[0] }}行 × {{ report.dataset_shape[1] }}列
                </span>
                <span class="meta-item">
                  <el-icon>
                    <PictureRounded />
                  </el-icon>
                  图表: {{ report.figures?.length || 0 }}个
                </span>
              </div>
            </div>
            <div class="report-actions">
              <el-button size="small" @click="viewReport(report)">
                <el-icon>
                  <View />
                </el-icon>
                查看
              </el-button>
              <el-button size="small" @click="exportReport(report)">
                <el-icon>
                  <Download />
                </el-icon>
                导出
              </el-button>
            </div>
          </div>

          <div class="report-preview">
            <div class="report-summary">
              {{ getReportSummary(report.report) }}
            </div>
            <div v-if="report.figures && report.figures.length > 0" class="report-charts">
              <el-image v-for="(figure, index) in report.figures.slice(0, 3)" :key="index"
                :src="`data:image/png;base64,${figure.data}`" class="chart-thumbnail" fit="cover"
                :preview-src-list="[`data:image/png;base64,${figure.data}`]" />
            </div>
          </div>
        </el-card>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <el-skeleton :rows="3" animated />
      </div>
    </div>

    <!-- 报告详情对话框 -->
    <el-dialog v-model="showReportDialog" title="分析报告详情" width="80%" class="report-dialog">
      <div v-if="selectedReport" class="report-detail">
        <div class="report-content">
          <div v-html="formatMarkdown(selectedReport.report)" class="markdown-content"></div>
        </div>
        <div v-if="selectedReport.figures && selectedReport.figures.length > 0" class="report-figures">
          <h4>分析图表</h4>
          <div class="figures-grid">
            <el-image v-for="(figure, index) in selectedReport.figures" :key="index"
              :src="`data:image/png;base64,${figure.data}`" class="figure-image" fit="contain"
              :preview-src-list="selectedReport.figures.map(f => `data:image/png;base64,${f.data}`)" />
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.reports-page {
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 16px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.header-content h1 {
  margin: 0 0 8px 0;
  font-size: 32px;
  font-weight: 600;
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.header-subtitle {
  margin: 0;
  color: #64748b;
  font-size: 16px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  backdrop-filter: blur(10px);
}

.empty-tip {
  color: #64748b;
  margin-top: 8px;
}

.reports-list {
  display: grid;
  gap: 24px;
}

.report-card {
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.report-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.report-info h3 {
  margin: 0 0 12px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
}

.report-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #64748b;
  font-size: 14px;
}

.report-preview {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 20px;
  align-items: start;
}

.report-summary {
  color: #475569;
  line-height: 1.6;
}

.report-charts {
  display: flex;
  gap: 8px;
}

.chart-thumbnail {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.loading-state {
  padding: 24px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 16px;
  backdrop-filter: blur(10px);
}

.markdown-content {
  line-height: 1.8;
  color: #374151;
}

.markdown-content h1,
.markdown-content h2,
.markdown-content h3 {
  color: #1f2937;
  margin-top: 24px;
  margin-bottom: 16px;
}

.markdown-content pre {
  background: #f8fafc;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.report-figures h4 {
  margin-bottom: 16px;
  color: #1f2937;
}

.figures-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.figure-image {
  width: 100%;
  height: 200px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}
</style>
