<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { UploadFilled, Plus } from '@element-plus/icons-vue'
import type { Dataset } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const appStore = useAppStore()

const datasets = ref<Dataset[]>([])
const isLoading = ref(false)

const fetchDatasets = async () => {
  isLoading.value = true
  try {
    // The store action now directly returns the array
    datasets.value = await appStore.getDatasets()
  } catch (error) {
    ElMessage.error('加载数据集列表失败')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

const handleFileUpload = async (options: any) => {
  const file = options.file
  if (!file) return

  isLoading.value = true
  try {
    await appStore.uploadFile(file)
    ElMessage.success('文件上传成功！')
    await fetchDatasets() // Refresh list after upload
  } catch (error) {
    ElMessage.error('文件上传失败')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

const openAddDatabase = () => {
  // Placeholder for adding a database connection
  ElMessageBox.prompt('请输入数据库连接URI', '添加数据库连接', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
  })
    .then(({ value }) => {
      // Logic to add database connection
      ElMessage.success(`连接信息已提交: ${value}`)
    })
    .catch(() => {
      ElMessage.info('已取消操作')
    })
}

const selectForAnalysis = (dataset: Dataset) => {
  appStore.setCurrentDataset(dataset)
  ElMessage.success(`已选择数据集 "${dataset.id.slice(0, 8)}..." 进行分析`)
  router.push('/chat-analysis')
}

onMounted(() => {
  fetchDatasets()
})
</script>

<template>
  <div class="data-management-container">
    <div class="header-actions">
      <el-upload class="action-card" drag action="#" :http-request="handleFileUpload" :show-file-list="false">
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          上传 CSV/Excel 文件
        </div>
        <template #tip>
          <div class="el-upload__tip">
            将文件拖到此处，或<em>点击上传</em>
          </div>
        </template>
      </el-upload>

      <div class="action-card" @click="openAddDatabase">
        <el-icon><Plus /></el-icon>
        <div class="action-text">
          添加数据库连接
        </div>
      </div>
    </div>

    <div class="data-list-section">
      <h2>可用数据源</h2>
      <el-table :data="datasets" v-loading="isLoading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="180">
          <template #default="{ row }">
            <code>{{ row.id }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="selectForAnalysis(row)">
              分析
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.data-management-container {
  padding: 24px;
  background-color: #f9fafb;
}

.header-actions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.action-card {
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: #fff;

  .el-icon {
    font-size: 48px;
    color: #c0c4cc;
    margin-bottom: 16px;
  }
  .action-text, .el-upload__text {
    color: #606266;
    font-size: 16px;
    font-weight: 500;
  }
  .el-upload__tip {
    color: #909399;
    font-size: 12px;
  }

  &:hover {
    border-color: #409eff;
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.1);
  }
}

.el-upload.action-card {
  display: block;
  :deep(.el-upload-dragger) {
    border: none;
    padding: 24px;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background-color: transparent;
  }
}

.data-list-section {
  background-color: #fff;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);

  h2 {
    margin-top: 0;
    margin-bottom: 20px;
    font-size: 20px;
    color: #303133;
  }
}
</style> 