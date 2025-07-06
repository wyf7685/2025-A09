<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { marked } from 'marked';
import { computed, onMounted, ref } from 'vue';
import { useAppStore } from '../stores/app';
import type { AnalysisReport } from '@/types';

// 定义类型接口
const appStore = useAppStore()

// 响应式数据
const analysisResult = ref<AnalysisReport | null>(null)
const analysisHistory = ref<AnalysisReport[]>([])
const progress = ref<number>(0)
const progressStatus = ref<'' | 'success' | 'exception'>('')
const currentStep = ref<string>('')
const exporting = ref<boolean>(false)

// 计算属性
const currentDataset = computed(() => appStore.currentDataset)

// 方法
const runAnalysis = async (): Promise<void> => {
  if (!currentDataset.value) {
    ElMessage.warning('请先选择数据集')
    return
  }

  try {
    // 开始分析进度模拟
    startProgressSimulation()

    const result = await appStore.runGeneralAnalysis(appStore.currentSessionId)

    analysisResult.value = result
    progress.value = 100
    progressStatus.value = 'success'
    currentStep.value = '分析完成！'

    ElMessage.success('自动分析完成！')

    // 添加到历史记录
    analysisHistory.value.unshift({
      ...result,
      timestamp: new Date().toISOString(),
      dataset_shape: currentDataset.value ? [
        currentDataset.value.row_count || 0,
        currentDataset.value.columns?.length || 0,
      ] : [0, 0],
    })

  } catch (error) {
    console.error('自动分析失败:', error)
    progress.value = 0
    progressStatus.value = 'exception'
    currentStep.value = '分析失败'
  }
}

const startProgressSimulation = (): void => {
  progress.value = 0
  progressStatus.value = ''

  const steps: Array<{ progress: number; message: string }> = [
    { progress: 20, message: '正在加载数据...' },
    { progress: 40, message: '正在进行基础统计分析...' },
    { progress: 60, message: '正在生成相关性矩阵...' },
    { progress: 80, message: '正在创建可视化图表...' },
    { progress: 95, message: '正在生成分析报告...' }
  ]

  let stepIndex = 0
  const interval = setInterval(() => {
    if (stepIndex < steps.length) {
      progress.value = steps[stepIndex].progress
      currentStep.value = steps[stepIndex].message
      stepIndex++
    } else {
      clearInterval(interval)
    }
  }, 1000)
}

const formatReport = async (report: string | undefined): Promise<string> => {
  if (!report) return ''
  return await marked(report)
}

const formatDate = (row: any, column: any, cellValue: string | undefined): string => {
  if (!cellValue) return '-'
  return new Date(cellValue).toLocaleString('zh-CN')
}

const viewAnalysis = (analysis: AnalysisReport): void => {
  analysisResult.value = analysis
  ElMessage.success('已切换到该分析结果')
}

const deleteAnalysis = async (analysis: AnalysisReport, index: number): Promise<void> => {
  try {
    await ElMessageBox.confirm('确定删除此分析记录？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    analysisHistory.value.splice(index, 1)
    ElMessage.success('分析记录已删除')

  } catch {
    // 用户取消删除
  }
}

const exportReport = async (format: 'markdown' | 'pdf' | 'html'): Promise<void> => {
  if (!analysisResult.value) {
    ElMessage.warning('没有分析结果可以导出')
    return
  }

  exporting.value = true
  try {
    await appStore.exportReport(format)
    ElMessage.success(`报告已导出为 ${format.toUpperCase()} 格式`)
  } catch (error) {
    console.error('导出失败:', error)
  } finally {
    exporting.value = false
  }
}

// 生命周期
onMounted(() => {
  // 从 store 中加载分析历史
  analysisHistory.value = appStore.analysisResults || []
})
</script>

<template>
  <div class="auto-analysis">
    <div class="analysis-card">
      <h2 style="margin-bottom: 20px;">
        <el-icon style="margin-right: 8px;">
          <DataAnalysis />
        </el-icon>
        自动数据分析
      </h2>

      <!-- 分析配置 -->
      <div style="margin-bottom: 24px;">
        <el-alert title="自动分析说明" type="info" description="自动分析功能将对您的数据集进行全面的统计分析，包括数据概览、统计特征、相关性分析、异常检测等，并生成完整的分析报告。"
          show-icon :closable="false" style="margin-bottom: 20px;" />

        <div class="toolbar">
          <div>
            <el-tag v-if="currentDataset" type="success">
              当前数据集: {{ currentDataset.id }}
            </el-tag>
            <el-tag v-else type="warning">
              未选择数据集
            </el-tag>
          </div>

          <div>
            <el-button type="primary" @click="runAnalysis" :loading="appStore.loading" :disabled="!currentDataset"
              size="large">
              <el-icon>
                <Play />
              </el-icon>
              {{ appStore.loading ? '分析中...' : '开始自动分析' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 分析进度 -->
    <div class="analysis-card" v-if="appStore.loading">
      <h3 style="margin-bottom: 16px;">分析进度</h3>
      <el-progress :percentage="progress" :status="progressStatus">
        <template #default="{ percentage }">
          <span style="color: #409EFF;">{{ percentage }}%</span>
        </template>
      </el-progress>
      <p style="margin-top: 12px; color: #666;">{{ currentStep }}</p>
    </div>

    <!-- 分析结果 -->
    <div class="analysis-card" v-if="analysisResult">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h3>分析结果</h3>
        <div>
          <el-button @click="exportReport('markdown')" :loading="exporting">
            <el-icon>
              <Download />
            </el-icon>
            导出 Markdown
          </el-button>
          <el-button @click="exportReport('html')" :loading="exporting">
            <el-icon>
              <Download />
            </el-icon>
            导出 HTML
          </el-button>
        </div>
      </div>

      <!-- 分析报告内容 -->
      <div class="report-content">
        <div v-html="formatReport(analysisResult.report)" class="report-text"></div>

        <!-- 图表展示 -->
        <div v-if="analysisResult.figures && analysisResult.figures.length > 0" class="figures-section">
          <h4 style="margin: 24px 0 16px 0;">生成的图表</h4>
          <el-row :gutter="16">
            <el-col :span="12" v-for="(figure, index) in analysisResult.figures" :key="index"
              style="margin-bottom: 16px;">
              <el-card>
                <template #header>
                  <span>图表 {{ index + 1 }}</span>
                </template>
                <div style="text-align: center;">
                  <img :src="`data:image/png;base64,${figure.data}`" :alt="`分析图表 ${index + 1}`"
                    style="max-width: 100%; border-radius: 4px;" />
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </div>
    </div>

    <!-- 历史分析记录 -->
    <div class="analysis-card" v-if="analysisHistory.length > 0">
      <h3 style="margin-bottom: 16px;">历史分析记录</h3>
      <el-table :data="analysisHistory" style="width: 100%">
        <el-table-column prop="timestamp" label="分析时间" :formatter="formatDate" />
        <el-table-column prop="dataset_shape" label="数据规模">
          <template #default="scope">
            {{ scope.row.dataset_shape?.[0] || 0 }} 行 × {{ scope.row.dataset_shape?.[1] || 0 }} 列
          </template>
        </el-table-column>
        <el-table-column prop="figures" label="图表数量">
          <template #default="scope">
            {{ scope.row.figures?.length || 0 }} 个
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button size="small" @click="viewAnalysis(scope.row)">
              查看详情
            </el-button>
            <el-button size="small" @click="deleteAnalysis(scope.row, scope.$index)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分析建议 -->
    <div class="analysis-card" v-if="!analysisResult && !appStore.loading">
      <h3 style="margin-bottom: 16px;">分析建议</h3>
      <el-row :gutter="16">
        <el-col :span="8">
          <el-card class="suggestion-card">
            <h4>📊 数据概览</h4>
            <p>获取数据的基本统计信息、数据类型、缺失值等概览信息</p>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="suggestion-card">
            <h4>🔗 相关性分析</h4>
            <p>分析数据各列之间的相关性，发现潜在的关联关系</p>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="suggestion-card">
            <h4>📈 趋势分析</h4>
            <p>分析数据的分布特征、趋势变化和异常值检测</p>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<style scoped>
.auto-analysis {
  max-width: 1200px;
  margin: 0 auto;
}

.report-content {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin-top: 16px;
}

.report-text {
  line-height: 1.8;
  color: #333;
}

.report-text h1,
.report-text h2,
.report-text h3,
.report-text h4,
.report-text h5,
.report-text h6 {
  color: #2c3e50;
  margin: 16px 0 12px 0;
}

.report-text pre {
  background: white;
  border: 1px solid #e1e8ed;
  border-radius: 4px;
  padding: 12px;
  overflow-x: auto;
}

.report-text code {
  background: #f1f3f4;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
}

.figures-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e4e7ed;
}

.suggestion-card {
  height: 140px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.suggestion-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.suggestion-card .el-card__body {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.suggestion-card h4 {
  margin-bottom: 8px;
  color: #409EFF;
}

.suggestion-card p {
  color: #666;
  font-size: 14px;
  line-height: 1.5;
}
</style>
