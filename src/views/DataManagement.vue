<script setup lang="ts">
import { useDataSourceStore } from '@/stores/datasource'
import { useSessionStore } from '@/stores/session'
import type { DataSourceMetadataWithID } from '@/types'
import {
  Connection,
  Delete,
  DocumentCopy,
  Edit,
  InfoFilled,
  Refresh,
  Search,
  UploadFilled,
  View
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

const fetchDatasets = async () => {
  isLoading.value = true
  try {
    datasources.value = await dataSourceStore.listDataSources()
  } catch (error) {
    ElMessage.error('加载数据集列表失败')
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

  isLoading.value = true
  try {
    await dataSourceStore.uploadCsvSource(file)
    ElMessage.success('文件上传成功！')
    await fetchDatasets()
  } catch (error) {
    ElMessage.error('文件上传失败')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

const openAddDatabase = () => {
  ElMessageBox.prompt('请输入数据库连接URI', '添加数据库连接', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
  })
    .then(({ value }) => {
      ElMessage.success(`连接信息已提交: ${value}`)
    })
    .catch(() => {
      ElMessage.info('已取消操作')
    })
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

// 过滤数据源
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
        <el-button
          type="primary"
          :icon="Refresh"
          @click="fetchDatasets"
          :loading="isLoading"
        >
          刷新列表
        </el-button>
      </div>
    </div>

    <!-- 上传区域 -->
    <div class="upload-section">
      <el-row :gutter="24">
        <el-col :xs="24" :sm="12" :md="8">
          <div class="upload-card">
            <el-upload
              class="upload-area"
              drag
              action="#"
              :http-request="handleFileUpload"
              :show-file-list="false"
            >
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
            <el-input
              v-model="searchQuery"
              placeholder="搜索数据源名称或描述..."
              :prefix-icon="Search"
              clearable
              @input="updateDisplayData"
              style="width: 300px"
            />
          </div>
        </div>
      </el-card>
    </div>

    <!-- 数据源列表 -->
    <div class="data-list-section">
      <el-card shadow="never">
        <el-table
          :data="paginatedDataSources"
          v-loading="isLoading"
          stripe
          class="data-table"
        >
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
                <el-button
                  size="small"
                  type="primary"
                  :icon="View"
                  @click="selectForAnalysis(row)"
                  plain
                >
                  分析
                </el-button>
                <el-button
                  size="small"
                  type="success"
                  :icon="InfoFilled"
                  @click="openPreviewDialog(row)"
                  plain
                >
                  预览
                </el-button>
                <el-button
                  size="small"
                  type="warning"
                  :icon="Edit"
                  @click="openEditDialog(row)"
                  plain
                >
                  编辑
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  :icon="Delete"
                  @click="deleteDataSource(row)"
                  plain
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页器 -->
        <div class="pagination-section">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[5, 10, 20, 50]"
            :small="false"
            :disabled="isLoading"
            :background="true"
            layout="total, sizes, prev, pager, next, jumper"
            :total="filteredDataSources.length"
            @current-change="updatePaginatedDataSources"
            @size-change="updatePaginatedDataSources"
          />
        </div>
      </el-card>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑数据源信息"
      width="500px"
      :before-close="() => editDialogVisible = false"
    >
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" placeholder="请输入数据源名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="editForm.description"
            type="textarea"
            placeholder="请输入数据源描述"
            :rows="3"
          />
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
    <el-dialog
      v-model="previewDialogVisible"
      :title="`预览数据源: ${currentEditSource?.name || ''}`"
      width="90%"
      :before-close="() => previewDialogVisible = false"
    >
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
          <el-table
            :data="previewData"
            v-loading="previewLoading"
            stripe
            border
            height="400"
          >
            <el-table-column
              v-for="column in previewColumns"
              :key="column"
              :prop="column"
              :label="column"
              show-overflow-tooltip
              min-width="120"
            />
          </el-table>
        </div>

        <div class="preview-pagination">
          <el-pagination
            v-model:current-page="previewPagination.current"
            v-model:page-size="previewPagination.pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :small="false"
            :disabled="previewLoading"
            :background="true"
            layout="total, sizes, prev, pager, next, jumper"
            :total="previewPagination.total"
            @current-change="loadPreviewData"
            @size-change="loadPreviewData"
          />
        </div>
      </div>
    </el-dialog>
  </div>
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
</style>
