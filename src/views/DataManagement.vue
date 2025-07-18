<script setup lang="ts">
import AddDatabaseDialog from '@/components/AddDatabaseDialog.vue'
import { useDataSourceStore } from '@/stores/datasource'
import { useSessionStore } from '@/stores/session'
import type { DataSourceMetadataWithID } from '@/types'
import api, { cleaningAPI, type CleaningAction, type CleaningSuggestion, type DataQualityReport } from '@/utils/api'
import {
  ArrowDown, ArrowRight, Back, Check, CircleCheck, CircleClose, Connection, DataAnalysis, Delete, Document, DocumentChecked, DocumentCopy, Edit,
  EditPen, Grid, InfoFilled, QuestionFilled, Refresh, RefreshRight, Search, Upload, UploadFilled, View, Warning
} from '@element-plus/icons-vue'
import { ElDialog, ElMessage, ElMessageBox, ElPagination, ElTable, ElTableColumn } from 'element-plus'
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();

const datasources = ref<DataSourceMetadataWithID[]>([])
const filteredDataSources = ref<DataSourceMetadataWithID[]>([])
const paginatedDataSources = ref<DataSourceMetadataWithID[]>([])
const isLoading = ref(false)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(10)

// 对话框相关
const editDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const addDatabaseDialogVisible = ref(false)
const currentEditSource = ref<DataSourceMetadataWithID | null>(null)
const editForm = ref({
  name: '',
  description: ''
})

// 预览数据
const previewData = ref<any[]>([])
const previewColumns = ref<string[]>([])
const previewLoading = ref(false)
const previewPagination = ref({
  current: 1,
  pageSize: 10,
  total: 0
})

// 数据清洗弹窗相关
const dataCleaningDialogVisible = ref(false)
const currentUploadFile = ref<File | null>(null)
const dataQualityReport = ref<DataQualityReport | null>(null)
const cleaningSuggestions = ref<CleaningSuggestion[]>([])
const fieldMappings = ref<Record<string, string>>({})
const isAnalyzing = ref(false)
const isCleaning = ref(false)
const fileMetadata = ref({
  name: '',
  description: ''
})
const userRequirements = ref('')
const selectedCleaningActions = ref<CleaningAction[]>([])
const cleaningStep = ref<'upload' | 'analysis' | 'cleaning' | 'complete'>('upload')
const analysisResult = ref<any>(null)

// 智能分析相关
const isSmartAnalyzing = ref(false)
const showAdvancedOptions = ref(false)
const selectedModel = ref('')
const availableModels = ref([
  { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (推荐)' },
  { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
  { value: 'gpt-4', label: 'GPT-4' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
])

const fetchDatasets = async () => {
  isLoading.value = true
  try {
    const sources = await dataSourceStore.listDataSources()
    datasources.value = sources
    updateFilteredDataSources()
  } catch (error) {
    ElMessage.error('获取数据源列表失败')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

const sourceTypeHumanRepr = (metadata: DataSourceMetadataWithID) => {
  if (!metadata.source_type.startsWith('dremio:')) {
    return metadata.source_type
  }
  const type = metadata.source_type.split(':')[1]
  switch (type) {
    case 'PROMOTED':
    case 'FILE':
      const parts = metadata.id.split('_')
      const fileExt = parts[parts.length - 1].toLowerCase()
      return fileExt === 'csv' ? 'CSV 文件' : ['xls', 'xlsx'].includes(fileExt) ? 'Excel 文件' : 'Dremio 数据集'
    case 'DIRECT':
      return '数据库表'
  }
  return type
}

const handleFileUpload = async (options: any) => {
  const file = options.file
  if (!file) return

  // 检查文件类型
  const allowedTypes = ['csv', 'xlsx', 'xls']
  const fileExtension = file.name.split('.').pop()?.toLowerCase()

  if (!allowedTypes.includes(fileExtension)) {
    ElMessage.error('只支持 CSV 和 Excel 文件格式')
    return
  }

  // 存储文件信息并显示清洗弹窗
  currentUploadFile.value = file
  fileMetadata.value.name = file.name.replace(/\.[^/.]+$/, '') // 移除文件扩展名
  fileMetadata.value.description = ''
  userRequirements.value = ''
  selectedModel.value = availableModels.value[0].value
  dataCleaningDialogVisible.value = true
  cleaningStep.value = 'upload'

  // 重置状态
  dataQualityReport.value = null
  cleaningSuggestions.value = []
  fieldMappings.value = {}
  selectedCleaningActions.value = []
  analysisResult.value = null
}

const openAddDatabase = () => {
  addDatabaseDialogVisible.value = true
}

const onDatabaseAddSuccess = async () => {
  ElMessage.success('数据库连接添加成功')
  await fetchDatasets() // 刷新数据源列表
}

const selectForAnalysis = async (metadata: DataSourceMetadataWithID) => {
  const session = await sessionStore.createSession(metadata.source_id)
  sessionStore.setCurrentSession(session)
  ElMessage.success(`已选择数据集 "${metadata.name.slice(0, 8)}..." 进行分析`)
  router.push('/chat-analysis')
}

// 编辑数据源
const openEditDialog = (source: DataSourceMetadataWithID) => {
  currentEditSource.value = source
  editForm.value = {
    name: source.name,
    description: source.description || ''
  }
  editDialogVisible.value = true
}

const saveEdit = async () => {
  if (!currentEditSource.value) return

  try {
    await dataSourceStore.updateDataSource(currentEditSource.value.source_id, {
      name: editForm.value.name,
      description: editForm.value.description
    })
    ElMessage.success('数据源信息更新成功')
    editDialogVisible.value = false
    await fetchDatasets()
  } catch (error) {
    ElMessage.error('更新失败')
    console.error(error)
  }
}

// 删除数据源
const deleteDataSource = async (source: DataSourceMetadataWithID) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除数据源 "${source.name}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await dataSourceStore.deleteDataSource(source.source_id)
    ElMessage.success('数据源删除成功')
    await fetchDatasets()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

// 预览数据
const openPreviewDialog = async (source: DataSourceMetadataWithID) => {
  currentEditSource.value = source
  previewDialogVisible.value = true
  await loadPreviewData(1)
}

const loadPreviewData = async (page: number = 1) => {
  if (!currentEditSource.value) return

  previewLoading.value = true
  try {
    const skip = (page - 1) * previewPagination.value.pageSize
    const result = await dataSourceStore.getSourceData(
      currentEditSource.value.source_id,
      skip,
      previewPagination.value.pageSize
    )

    previewData.value = result.data
    previewPagination.value.total = result.total
    previewPagination.value.current = page

    if (result.data.length > 0) {
      previewColumns.value = Object.keys(result.data[0])
    }
  } catch (error) {
    ElMessage.error('加载预览数据失败')
    console.error(error)
  } finally {
    previewLoading.value = false
  }
}

// 智能数据质量分析
const analyzeDataQualityWithAI = async () => {
  if (!currentUploadFile.value) return

  isSmartAnalyzing.value = true
  cleaningStep.value = 'analysis'

  try {
    // 使用新的智能Agent API
    const result = await cleaningAPI.analyzeDataQuality(
      currentUploadFile.value,
      userRequirements.value || undefined,
      selectedModel.value || undefined
    )

    if (result.success) {
      analysisResult.value = result
      dataQualityReport.value = result.quality_report || null
      cleaningSuggestions.value = result.cleaning_suggestions || []
      fieldMappings.value = result.field_mappings || {}

      ElMessage.success('智能数据质量分析完成！')
    } else {
      throw new Error(result.error || '分析失败')
    }
  } catch (error) {
    ElMessage.error('智能数据质量分析失败')
    console.error(error)
    cleaningStep.value = 'upload'
  } finally {
    isSmartAnalyzing.value = false
  }
}

// 传统数据质量分析（保持向后兼容）
const analyzeDataQuality = async () => {
  if (!currentUploadFile.value) return

  isAnalyzing.value = true
  cleaningStep.value = 'analysis'

  try {
    // 获取数据质量报告
    const result = await cleaningAPI.checkDataQuality(currentUploadFile.value)
    dataQualityReport.value = result.quality_check || null
    cleaningSuggestions.value = result.cleaning_suggestions || []

  } catch (error) {
    ElMessage.error('数据质量分析失败')
    console.error(error)
    cleaningStep.value = 'upload'
  } finally {
    isAnalyzing.value = false
  }
}

// 应用清洗动作（记录用户选择）
const applyCleaningActions = async () => {
  if (selectedCleaningActions.value.length === 0) {
    ElMessage.warning('请选择至少一个清洗建议')
    return
  }

  isCleaning.value = true
  try {
    // 模拟记录用户选择的过程
    await new Promise(resolve => setTimeout(resolve, 1000))

    ElMessage.success(`已记录 ${selectedCleaningActions.value.length} 个清洗建议选择`)
    cleaningStep.value = 'complete'
  } catch (error) {
    ElMessage.error('记录清洗选择失败')
    console.error(error)
  } finally {
    isCleaning.value = false
  }
}

// 跳过清洗直接上传
const skipCleaningAndUpload = async () => {
  if (!currentUploadFile.value) return

  isLoading.value = true
  try {
    // 直接使用原始文件，通过参数传递用户修改的文件名
    await dataSourceStore.uploadFileSource(
      currentUploadFile.value, 
      fileMetadata.value.description,
      fileMetadata.value.name
    )
    ElMessage.success('文件上传成功！')
    dataCleaningDialogVisible.value = false
    await fetchDatasets()
  } catch (error) {
    ElMessage.error('文件上传失败')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

// 完成清洗并上传
const completeCleaningAndUpload = async () => {
  if (!currentUploadFile.value) return

  isLoading.value = true
  try {
    // 直接使用原始文件，通过参数传递用户修改的文件名
    const uploadResult = await dataSourceStore.uploadFileSource(
      currentUploadFile.value, 
      fileMetadata.value.description,
      fileMetadata.value.name
    )

    // 如果有字段映射，保存到数据源
    if (Object.keys(fieldMappings.value).length > 0 && uploadResult?.source_id) {
      try {
        await cleaningAPI.saveFieldMappings(uploadResult.source_id, fieldMappings.value)
        ElMessage.success('文件上传成功，字段映射已保存！')
      } catch (mappingError) {
        console.warn('字段映射保存失败:', mappingError)
        ElMessage.success('文件上传成功，但字段映射保存失败')
      }
    } else {
      ElMessage.success('文件上传成功！')
    }

    dataCleaningDialogVisible.value = false
    await fetchDatasets()
  } catch (error) {
    ElMessage.error('文件上传失败')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

// 切换清洗动作选择
const toggleCleaningAction = (suggestion: CleaningSuggestion) => {
  const action: CleaningAction = {
    type: suggestion.type,
    column: suggestion.column,
    parameters: suggestion.options?.[0]?.method || '' // 默认选择第一个选项的方法
  }

  const index = selectedCleaningActions.value.findIndex(a =>
    a.type === action.type && a.column === action.column
  )

  if (index >= 0) {
    selectedCleaningActions.value.splice(index, 1)
  } else {
    selectedCleaningActions.value.push(action)
  }
}

// 检查清洗动作是否已选择
const isCleaningActionSelected = (suggestion: CleaningSuggestion) => {
  return selectedCleaningActions.value.some(a =>
    a.type === suggestion.type && a.column === suggestion.column
  )
}

// 关闭清洗弹窗
const closeCleaningDialog = () => {
  dataCleaningDialogVisible.value = false
  currentUploadFile.value = null
  dataQualityReport.value = null
  cleaningSuggestions.value = []
  fieldMappings.value = {}
  selectedCleaningActions.value = []
  cleaningStep.value = 'upload'
  fileMetadata.value = { name: '', description: '' }
  userRequirements.value = ''
  analysisResult.value = null
  showAdvancedOptions.value = false
}

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

const updateFilteredDataSources = () => {
  let filtered = datasources.value

  if (searchQuery.value) {
    filtered = filtered.filter(ds =>
      ds.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      ds.description?.toLowerCase().includes(searchQuery.value.toLowerCase())
    )
  }

  filteredDataSources.value = filtered
}

// 分页数据
const updatePaginatedDataSources = () => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  paginatedDataSources.value = filteredDataSources.value.slice(start, end)
}

// 监听数据变化
const updateDisplayData = () => {
  updateFilteredDataSources()
  updatePaginatedDataSources()
}

// 获取类型标签颜色
const getTypeTagType = (source: DataSourceMetadataWithID) => {
  const type = sourceTypeHumanRepr(source)
  if (type.includes('CSV')) return 'success'
  if (type.includes('Excel')) return 'warning'
  if (type.includes('数据库')) return 'danger'
  return 'info'
}

onMounted(() => {
  fetchDatasets()
})

// 使用 watch 监听数据变化
watch(datasources, updateDisplayData, { deep: true })
watch(searchQuery, updateDisplayData)
watch(currentPage, updatePaginatedDataSources)
watch(pageSize, updatePaginatedDataSources)
</script>

<template>
  <div class="data-management-container">
    <!-- 顶部操作区域 -->
    <div class="header-section">
      <div class="header-title">
        <h1>数据源管理</h1>
        <p>上传、管理和分析您的数据源</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :icon="Refresh" @click="fetchDatasets" :loading="isLoading">
          刷新列表
        </el-button>
      </div>
    </div>

    <!-- 上传区域 -->
    <div class="upload-section">
      <el-row :gutter="24">
        <el-col :xs="24" :sm="12" :md="8">
          <div class="upload-card">
            <el-upload class="upload-area" drag action="#" :http-request="handleFileUpload" :show-file-list="false">
              <el-icon class="upload-icon">
                <upload-filled />
              </el-icon>
              <div class="upload-text">
                <div class="upload-title">上传 CSV/Excel 文件</div>
                <div class="upload-hint">将文件拖到此处，或点击上传</div>
              </div>
            </el-upload>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="8">
          <div class="action-card" @click="openAddDatabase">
            <el-icon class="card-icon">
              <Connection />
            </el-icon>
            <div class="card-content">
              <div class="card-title">添加数据库连接</div>
              <div class="card-description">连接到外部数据库</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 搜索和过滤区域 -->
    <div class="search-section">
      <el-card shadow="never">
        <div class="search-header">
          <h3>数据源列表</h3>
          <div class="search-controls">
            <el-input v-model="searchQuery" placeholder="搜索数据源名称或描述..." :prefix-icon="Search" clearable
              @input="updateDisplayData" style="width: 300px" />
          </div>
        </div>
      </el-card>
    </div>

    <!-- 数据源列表 -->
    <div class="data-list-section">
      <el-card shadow="never">
        <el-table :data="paginatedDataSources" v-loading="isLoading" stripe class="data-table">
          <el-table-column prop="source_id" label="ID" width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.source_id.slice(0, 8) }}...</el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="name" label="名称" min-width="200">
            <template #default="{ row }">
              <div class="name-cell">
                <el-icon class="name-icon">
                  <DocumentCopy />
                </el-icon>
                <span class="name-text">{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="source_type" label="类型" width="130">
            <template #default="{ row }">
              <el-tag size="small" :type="getTypeTagType(row)">
                {{ sourceTypeHumanRepr(row) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="description-text">
                {{ row.description || '暂无描述' }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="统计信息" width="120" align="center">
            <template #default="{ row }">
              <div class="stats-cell">
                <el-tooltip content="行数" placement="top">
                  <el-tag size="small" type="success">
                    {{ row.row_count || 'N/A' }}
                  </el-tag>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="240" align="center">
            <template #default="{ row }">
              <div class="action-buttons">
                <el-button size="small" type="primary" :icon="View" @click="selectForAnalysis(row)" plain>
                  分析
                </el-button>
                <el-button size="small" type="success" :icon="InfoFilled" @click="openPreviewDialog(row)" plain>
                  预览
                </el-button>
                <el-button size="small" type="warning" :icon="Edit" @click="openEditDialog(row)" plain>
                  编辑
                </el-button>
                <el-button size="small" type="danger" :icon="Delete" @click="deleteDataSource(row)" plain>
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页器 -->
        <div class="pagination-section">
          <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[5, 10, 20, 50]"
            :small="false" :disabled="isLoading" :background="true" layout="total, sizes, prev, pager, next, jumper"
            :total="filteredDataSources.length" @current-change="updatePaginatedDataSources"
            @size-change="updatePaginatedDataSources" />
        </div>
      </el-card>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑数据源信息" width="500px"
      :before-close="() => editDialogVisible = false">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" placeholder="请输入数据源名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" placeholder="请输入数据源描述" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="editDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveEdit">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="previewDialogVisible" :title="`预览数据源: ${currentEditSource?.name || ''}`" width="90%"
      :before-close="() => previewDialogVisible = false">
      <div class="preview-content">
        <div class="preview-header">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="数据源名称">
              {{ currentEditSource?.name }}
            </el-descriptions-item>
            <el-descriptions-item label="类型">
              {{ currentEditSource ? sourceTypeHumanRepr(currentEditSource) : '' }}
            </el-descriptions-item>
            <el-descriptions-item label="总行数">
              {{ previewPagination.total }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="preview-table">
          <el-table :data="previewData" v-loading="previewLoading" stripe border height="400">
            <el-table-column v-for="column in previewColumns" :key="column" :prop="column" :label="column"
              show-overflow-tooltip min-width="120" />
          </el-table>
        </div>

        <div class="preview-pagination">
          <el-pagination v-model:current-page="previewPagination.current" v-model:page-size="previewPagination.pageSize"
            :page-sizes="[10, 20, 50, 100]" :small="false" :disabled="previewLoading" :background="true"
            layout="total, sizes, prev, pager, next, jumper" :total="previewPagination.total"
            @current-change="loadPreviewData" @size-change="loadPreviewData" />
        </div>
      </div>
    </el-dialog>

    <!-- 数据清洗对话框 -->
    <el-dialog v-model="dataCleaningDialogVisible" title="数据清洗与分析" width="600px"
      :before-close="() => dataCleaningDialogVisible = false">
      <div class="cleaning-content">
        <!-- 步骤指示器 -->
        <div class="cleaning-steps">
          <div class="step" v-for="(step, index) in [
            { key: 'upload', name: '文件上传' },
            { key: 'analysis', name: '智能分析' },
            { key: 'cleaning', name: '清洗建议' },
            { key: 'complete', name: '完成上传' }
          ]" :key="step.key" :class="{ active: cleaningStep === step.key }">
            <div class="step-icon">
              <el-icon>
                <Check v-if="cleaningStep !== 'upload' && cleaningStep !== step.key" />
                <CircleCheck v-else-if="cleaningStep === step.key" />
                <CircleClose v-else />
              </el-icon>
            </div>
            <div class="step-title">{{ step.name }}</div>
          </div>
        </div>

        <!-- 上传文件信息 -->
        <div v-if="cleaningStep === 'upload'" class="upload-info">
          <div class="file-details">
            <div class="file-icon">
              <el-icon size="48" color="#667eea">
                <Document />
              </el-icon>
            </div>
            <div class="file-meta">
              <div class="file-name">{{ fileMetadata.name }}</div>
              <div class="file-size">{{ currentUploadFile ? (currentUploadFile.size / 1024 / 1024).toFixed(2) : 0 }} MB
              </div>
              <div class="file-type">{{ currentUploadFile?.name.split('.').pop()?.toUpperCase() }} 文件</div>
            </div>
          </div>

          <!-- 文件元数据编辑 -->
          <div class="file-metadata">
            <el-form :model="fileMetadata" label-width="80px" label-position="top">
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
                  placeholder="例如：请重点关注数据标准化，确保所有列名都符合命名规范，处理缺失值，并验证邮箱格式..." :rows="3" show-word-limit
                  maxlength="500" />
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
            <el-button @click="closeCleaningDialog" size="large">
              取消
            </el-button>
            <el-button type="primary" @click="skipCleaningAndUpload" :loading="isLoading" size="large">
              <el-icon>
                <Upload />
              </el-icon>
              跳过分析，直接上传
            </el-button>
            <el-button type="success" @click="analyzeDataQualityWithAI" :loading="isSmartAnalyzing" size="large">
              <el-icon>
                <DataAnalysis />
              </el-icon>
              开始智能分析
            </el-button>
          </div>
        </div>

        <!-- 数据质量分析结果 -->
        <div v-if="cleaningStep === 'analysis'" class="analysis-results">
          <div v-if="isSmartAnalyzing" class="loading-status">
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
                <h3>智能分析结果</h3>
                <el-tag :type="getQualityScoreColor(analysisResult?.quality_score || 0)" size="large">
                  {{ analysisResult?.quality_score || 0 }}分 - {{ getQualityScoreText(analysisResult?.quality_score || 0)
                  }}
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
                      <el-tag type="info" size="small">原始</el-tag>
                      <span class="field-name">{{ originalName }}</span>
                    </div>
                    <el-icon class="arrow-icon">
                      <ArrowRight />
                    </el-icon>
                    <div class="suggested-field">
                      <el-tag type="success" size="small">建议</el-tag>
                      <span class="field-name">{{ suggestion }}</span>
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
                <el-button type="primary" @click="cleaningStep = 'cleaning'"
                  :disabled="cleaningSuggestions.length === 0" size="large">
                  <el-icon>
                    <ArrowRight />
                  </el-icon>
                  下一步：查看清洗建议 ({{ cleaningSuggestions.length }})
                </el-button>

                <el-button type="success" @click="skipCleaningAndUpload" size="large" :disabled="!dataQualityReport">
                  <el-icon>
                    <Upload />
                  </el-icon>
                  {{ cleaningSuggestions.length === 0 ? '直接上传' : '忽略问题并上传' }}
                </el-button>

                <el-button @click="cleaningStep = 'upload'" size="large">
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
        <div v-if="cleaningStep === 'cleaning'" class="cleaning-suggestions">
          <div v-if="isCleaning" class="cleaning-progress">
            <el-empty description="正在记录您的清洗选择，请稍候..." />
          </div>
          <div v-else>
            <div class="suggestions-header">
              <div class="header-content">
                <div class="title">选择数据清洗建议</div>
                <div class="subtitle">
                  根据数据质量分析结果，我们为您提供了以下清洗建议。请选择您认为合适的建议，系统将记录您的选择。
                </div>
              </div>

              <el-alert title="功能说明" description="本系统提供数据质量检测和清洗建议，但不会自动执行清洗操作。您可以根据这些建议手动优化您的数据文件。" type="info"
                show-icon :closable="false" />
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
                  记录选中的建议 ({{ selectedCleaningActions.length }})
                </el-button>

                <el-button @click="skipCleaningAndUpload" size="large">
                  <el-icon>
                    <Upload />
                  </el-icon>
                  跳过建议直接上传
                </el-button>

                <el-button @click="cleaningStep = 'analysis'" size="large">
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
                  <el-checkbox :checked="isCleaningActionSelected(suggestion)"
                    @change="toggleCleaningAction(suggestion)" size="large" />
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
        <div v-if="cleaningStep === 'complete'" class="complete-status">
          <el-result status="success" title="处理完成" :sub-title="selectedCleaningActions.length > 0 ?
            `已记录 ${selectedCleaningActions.length} 个清洗建议，您可以根据这些建议优化数据质量` :
            '数据质量检测完成，可以直接上传数据'">
            <template #extra>
              <div class="complete-actions">
                <el-button type="primary" @click="completeCleaningAndUpload" size="large">
                  <el-icon>
                    <Upload />
                  </el-icon>
                  确认上传数据
                </el-button>

                <el-button @click="analyzeDataQualityWithAI" size="large">
                  <el-icon>
                    <RefreshRight />
                  </el-icon>
                  重新智能分析数据质量
                </el-button>

                <el-button @click="cleaningStep = 'cleaning'" v-if="cleaningSuggestions.length > 0" size="large">
                  <el-icon>
                    <EditPen />
                  </el-icon>
                  修改清洗选择
                </el-button>
              </div>

              <div class="complete-summary" v-if="selectedCleaningActions.length > 0">
                <el-card class="summary-card">
                  <template #header>
                    <span>您选择的清洗建议摘要</span>
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
  </div>

  <AddDatabaseDialog v-model:visible="addDatabaseDialogVisible" @success="onDatabaseAddSuccess" />
</template>

<style lang="scss" scoped>
.data-management-container {
  padding: 24px;
  background: #f8fafc;
  min-height: 100vh;
}

// 顶部标题区域
.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;

  .header-title {
    h1 {
      font-size: 32px;
      font-weight: 700;
      color: #1f2937;
      margin: 0 0 8px 0;
      text-shadow: none;
    }

    p {
      font-size: 16px;
      color: #6b7280;
      margin: 0;
    }
  }

  .header-actions {
    .el-button {
      padding: 12px 24px;
      border-radius: 25px;
      font-weight: 600;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      transition: all 0.3s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
      }
    }
  }
}

// 上传区域
.upload-section {
  margin-bottom: 32px;

  .upload-card {
    background: white;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
    }

    .upload-area {
      width: 100%;

      :deep(.el-upload) {
        width: 100%;
      }

      :deep(.el-upload-dragger) {
        width: 100%;
        height: 200px;
        border: 2px dashed #e0e7ff;
        border-radius: 12px;
        background: linear-gradient(135deg, #f0f4ff 0%, #e0e7ff 100%);
        transition: all 0.3s ease;

        &:hover {
          border-color: #667eea;
          background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
        }
      }

      .upload-icon {
        font-size: 48px;
        color: #667eea;
        margin-bottom: 16px;
      }

      .upload-text {
        .upload-title {
          font-size: 18px;
          font-weight: 600;
          color: #374151;
          margin-bottom: 8px;
        }

        .upload-hint {
          font-size: 14px;
          color: #6b7280;
        }
      }
    }
  }

  .action-card {
    background: white;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    cursor: pointer;
    transition: all 0.3s ease;
    text-align: center;
    height: 248px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;

    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
      background: linear-gradient(135deg, #f0f4ff 0%, #e0e7ff 100%);
    }

    .card-icon {
      font-size: 48px;
      color: #667eea;
      margin-bottom: 16px;
    }

    .card-content {
      .card-title {
        font-size: 18px;
        font-weight: 600;
        color: #374151;
        margin-bottom: 8px;
      }

      .card-description {
        font-size: 14px;
        color: #6b7280;
      }
    }
  }
}

// 搜索区域
.search-section {
  margin-bottom: 24px;

  .el-card {
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    border: none;

    :deep(.el-card__body) {
      padding: 24px;
    }

    .search-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h3 {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
        color: #374151;
      }

      .search-controls {
        .el-input {
          :deep(.el-input__wrapper) {
            border-radius: 25px;
            padding: 8px 16px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
          }
        }
      }
    }
  }
}

// 数据列表区域
.data-list-section {
  .el-card {
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    border: none;

    :deep(.el-card__body) {
      padding: 24px;
    }

    .data-table {
      :deep(.el-table__header) {
        background: #f8fafc;

        th {
          background: #f8fafc !important;
          color: #374151;
          font-weight: 600;
          border-bottom: 2px solid #e5e7eb;
        }
      }

      :deep(.el-table__body) {
        tr {
          transition: all 0.3s ease;

          &:hover {
            background: #f0f4ff !important;
          }
        }
      }

      .name-cell {
        display: flex;
        align-items: center;

        .name-icon {
          color: #667eea;
          margin-right: 8px;
        }

        .name-text {
          font-weight: 600;
          color: #374151;
        }
      }

      .description-text {
        color: #6b7280;
        font-size: 14px;
      }

      .stats-cell {
        display: flex;
        justify-content: center;

        .el-tag {
          border-radius: 12px;
          font-weight: 600;
        }
      }

      .action-buttons {
        display: flex;
        gap: 8px;
        justify-content: center;
        flex-wrap: wrap;

        .el-button {
          border-radius: 20px;
          padding: 6px 12px;
          font-weight: 500;
          transition: all 0.3s ease;

          &:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          }
        }
      }
    }

    .pagination-section {
      display: flex;
      justify-content: center;
      margin-top: 24px;

      .el-pagination {
        :deep(.el-pagination__jump) {
          margin-left: 24px;
        }

        :deep(.btn-next),
        :deep(.btn-prev) {
          border-radius: 8px;
        }

        :deep(.el-pager) {
          li {
            border-radius: 8px;
            margin: 0 2px;

            &.is-active {
              background: #667eea;
              color: white;
            }
          }
        }
      }
    }
  }
}

// 对话框样式
.el-dialog {
  :deep(.el-dialog__header) {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 16px 16px 0 0;
    padding: 20px 24px;

    .el-dialog__title {
      font-weight: 600;
      font-size: 18px;
    }
  }

  :deep(.el-dialog__body) {
    padding: 24px;
  }

  :deep(.el-dialog__footer) {
    border-top: 1px solid #e5e7eb;
    padding: 16px 24px;

    .el-button {
      border-radius: 20px;
      padding: 8px 20px;
      font-weight: 500;
    }
  }
}

// 预览内容
.preview-content {
  .preview-header {
    margin-bottom: 24px;

    .el-descriptions {
      :deep(.el-descriptions__header) {
        background: #f8fafc;
      }

      :deep(.el-descriptions__body) {
        .el-descriptions__table {
          border-radius: 8px;
          overflow: hidden;
        }
      }
    }
  }

  .preview-table {
    margin-bottom: 24px;

    .el-table {
      border-radius: 8px;
      overflow: hidden;

      :deep(.el-table__header) {
        background: #f8fafc;
      }
    }
  }

  .preview-pagination {
    display: flex;
    justify-content: center;

    .el-pagination {
      :deep(.el-pager) {
        li {
          border-radius: 6px;
          margin: 0 2px;

          &.is-active {
            background: #667eea;
            color: white;
          }
        }
      }
    }
  }
}

// 数据清洗对话框内容
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
    padding: 24px;
    background: #f8fafc;
    border-radius: 12px;
    margin-bottom: 24px;

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

    .file-metadata {
      margin-bottom: 24px;
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

      .el-button {
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 500;
      }
    }
  }

  // 智能分析结果样式
  .smart-analysis-summary {
    margin-bottom: 24px;

    .summary-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;

      h3 {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
        color: #1f2937;
      }
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
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 12px;

      .mapping-card {
        padding: 16px;
        background: white;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        transition: all 0.2s ease;

        &:hover {
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .mapping-header {
          display: flex;
          align-items: center;
          gap: 12px;

          .original-field,
          .suggested-field {
            display: flex;
            align-items: center;
            gap: 8px;
            flex: 1;

            .field-name {
              font-weight: 500;
              color: #374151;
            }
          }

          .arrow-icon {
            color: #9ca3af;
            font-size: 14px;
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

  // 清洗建议样式
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

  // 分析操作区域样式
  .analysis-actions {
    margin-top: 24px;

    .action-info {
      margin-bottom: 16px;
    }

    .action-buttons {
      display: flex;
      gap: 12px;
      justify-content: center;

      .el-button {
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 500;
      }
    }
  }

  .file-size {
    font-size: 14px;
    color: #6b7280;
    background: #e5e7eb;
    padding: 4px 8px;
    border-radius: 6px;
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

.file-actions {
  display: flex;
  gap: 12px;

  .el-button {
    border-radius: 8px;
    padding: 12px 24px;
    font-weight: 500;
    transition: all 0.3s ease;

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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

      .el-alert {
        border-radius: 8px;
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

          .el-icon {
            margin-right: 6px;
          }
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

        .el-icon {
          margin-right: 8px;
        }
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

  // 响应式设计
  @media (max-width: 768px) {
    .data-management-container {
      padding: 16px;
    }

    .header-section {
      flex-direction: column;
      text-align: center;
      gap: 16px;

      .header-title {
        h1 {
          font-size: 24px;
        }
      }
    }

    .upload-section {
      .el-col {
        margin-bottom: 16px;
      }
    }

    .search-section {
      .search-header {
        flex-direction: column;
        gap: 16px;

        .search-controls {
          width: 100%;

          .el-input {
            width: 100% !important;
          }
        }
      }
    }

    .data-list-section {
      .action-buttons {
        flex-direction: column;
        gap: 4px;

        .el-button {
          width: 100%;
          font-size: 12px;
          padding: 4px 8px;
        }
      }
    }

    .cleaning-content {
      .cleaning-steps {
        flex-direction: column;

        .step {
          justify-content: center;
          padding-left: 0;
          padding-right: 0;

          .step-icon {
            left: auto;
            right: 0;
            top: 0;
            transform: none;
          }

          .step-title {
            font-size: 14px;
          }
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

      .analysis-results {
        .quality-report {
          margin-bottom: 16px;

          .report-header {
            flex-direction: column;
            align-items: flex-start;
            margin-bottom: 12px;

            .report-title {
              font-size: 16px;
            }

            .report-score {
              .score-tag {
                font-size: 14px;
              }
            }
          }

          .report-content {
            grid-template-columns: 1fr;
          }
        }

        .suggestions-header {
          margin-bottom: 12px;
        }

        .suggestions-list {
          .suggestion-item {
            flex-direction: column;
            align-items: flex-start;
            padding: 12px;
            gap: 8px;

            .item-content {
              .item-description {
                font-size: 14px;
              }

              .item-details {
                flex-direction: column;
                gap: 4px;

                .detail-item {
                  font-size: 12px;
                }
              }
            }
          }
        }
      }
    }
  }

  // 标签样式优化
  .el-tag {
    border-radius: 12px;
    font-weight: 500;
    padding: 4px 12px;

    &.el-tag--success {
      background: #ecfdf5;
      border-color: #10b981;
      color: #059669;
    }

    &.el-tag--warning {
      background: #fffbeb;
      border-color: #f59e0b;
      color: #d97706;
    }

    &.el-tag--danger {
      background: #fef2f2;
      border-color: #ef4444;
      color: #dc2626;
    }

    &.el-tag--info {
      background: #f0f9ff;
      border-color: #3b82f6;
      color: #2563eb;
    }
  }

  // 加载状态
  .el-loading-mask {
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(4px);
  }
}
</style>
