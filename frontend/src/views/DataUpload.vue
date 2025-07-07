<template>
  <div class="data-upload">
    <div class="analysis-card">
      <h2 style="margin-bottom: 20px;">
        <el-icon style="margin-right: 8px;"><Upload /></el-icon>
        数据上传
      </h2>
      
      <!-- 上传区域 -->
      <el-upload
        ref="uploadRef"
        class="upload-demo"
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :before-remove="beforeRemove"
        accept=".csv,.xlsx,.xls"
        :limit="1"
        :on-exceed="handleExceed"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将文件拖拽到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 CSV、Excel 文件，文件大小不超过 50MB
          </div>
        </template>
      </el-upload>
      
      <!-- 上传按钮 -->
      <div style="margin-top: 20px; text-align: center;">
        <el-button 
          type="primary" 
          @click="submitUpload"
          :loading="appStore.loading"
          :disabled="!selectedFile"
        >
          <el-icon><Upload /></el-icon>
          {{ appStore.loading ? '上传中...' : '开始上传' }}
        </el-button>
        <el-button @click="clearFiles">清空</el-button>
      </div>
    </div>

    <!-- 数据预览 -->
    <div class="analysis-card" v-if="uploadResult">
      <h3 style="margin-bottom: 16px;">数据预览</h3>
      
      <!-- 基本信息 -->
      <el-row :gutter="16" style="margin-bottom: 20px;">
        <el-col :span="6">
          <el-statistic title="数据行数" :value="uploadResult.overview.shape[0]" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="数据列数" :value="uploadResult.overview.shape[1]" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="数据集ID" :value="uploadResult.dataset_id" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="会话ID" :value="uploadResult.session_id.slice(0, 8) + '...'" />
        </el-col>
      </el-row>
      
      <!-- 列信息 -->
      <div style="margin-bottom: 20px;">
        <h4 style="margin-bottom: 12px;">列信息</h4>
        <el-table :data="columnInfo" style="width: 100%">
          <el-table-column prop="name" label="列名" />
          <el-table-column prop="dtype" label="数据类型" />
          <el-table-column prop="missing" label="缺失值" />
        </el-table>
      </div>
      
      <!-- 数据预览表格 -->
      <div>
        <h4 style="margin-bottom: 12px;">数据预览（前5行）</h4>
        <el-table 
          :data="uploadResult.overview.head" 
          style="width: 100%"
          max-height="400"
          border
        >
          <el-table-column
            v-for="column in uploadResult.overview.columns"
            :key="column"
            :prop="column"
            :label="column"
            show-overflow-tooltip
            min-width="120"
          />
        </el-table>
      </div>
      
      <!-- 操作按钮 -->
      <div style="margin-top: 20px; text-align: center;">
        <el-button type="primary" @click="$router.push('/chat-analysis')">
          <el-icon><ChatDotRound /></el-icon>
          开始对话分析
        </el-button>
        <el-button type="success" @click="$router.push('/auto-analysis')">
          <el-icon><DataAnalysis /></el-icon>
          运行自动分析
        </el-button>
      </div>
    </div>

    <!-- 历史上传记录 -->
    <div class="analysis-card" v-if="uploadHistory.length > 0">
      <h3 style="margin-bottom: 16px;">历史上传记录</h3>
      <el-table :data="uploadHistory" style="width: 100%">
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="uploaded_at" label="上传时间" :formatter="formatDate" />
        <el-table-column prop="rows" label="行数" />
        <el-table-column prop="columns" label="列数" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button 
              size="small" 
              @click="useDataset(scope.row)"
            >
              使用此数据集
            </el-button>
            <el-button 
              size="small" 
              type="danger" 
              @click="deleteDataset(scope.row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useAppStore } from '../stores/app'

const appStore = useAppStore()

// 响应式数据
const uploadRef = ref()
const selectedFile = ref(null)
const uploadResult = ref(null)
const uploadHistory = ref([])

// 计算属性
const columnInfo = computed(() => {
  if (!uploadResult.value) return []
  
  const { columns, dtypes, missing_values } = uploadResult.value.overview
  return columns.map(col => ({
    name: col,
    dtype: dtypes[col] || 'unknown',
    missing: missing_values[col] || 0
  }))
})

// 方法
const handleFileChange = (file) => {
  selectedFile.value = file
}

const handleExceed = () => {
  ElMessage.warning('只能选择一个文件！')
}

const beforeRemove = () => {
  return ElMessageBox.confirm('确定移除该文件？').catch(() => false)
}

const clearFiles = () => {
  uploadRef.value.clearFiles()
  selectedFile.value = null
  uploadResult.value = null
}

const submitUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  
  try {
    const result = await appStore.uploadFile(
      selectedFile.value.raw, 
      appStore.currentSessionId
    )
    
    uploadResult.value = result
    
    // 设置为当前数据集
    appStore.setCurrentDataset({
      id: result.dataset_id,
      overview: result.overview,
      uploaded_at: new Date().toISOString()
    })
    
    ElMessage.success('文件上传成功！')
    
    // 刷新历史记录
    await loadUploadHistory()
    
  } catch (error) {
    console.error('上传失败:', error)
  }
}

const formatDate = (row, column, cellValue) => {
  if (!cellValue) return '-'
  return new Date(cellValue).toLocaleString('zh-CN')
}

const useDataset = (dataset) => {
  appStore.setCurrentDataset(dataset)
  ElMessage.success('已切换到该数据集')
}

const deleteDataset = async (dataset) => {
  try {
    await ElMessageBox.confirm('确定删除该数据集？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    // 这里应该调用删除API，但后端没有提供此接口
    ElMessage.info('删除功能待后端支持')
    
  } catch {
    // 用户取消删除
  }
}

const loadUploadHistory = async () => {
  try {
    if (appStore.currentSessionId) {
      const result = await appStore.getDatasets(appStore.currentSessionId)
      uploadHistory.value = result.datasets || []
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
  }
}

// 生命周期
onMounted(() => {
  loadUploadHistory()
})
</script>

<style scoped>
.data-upload {
  max-width: 1000px;
  margin: 0 auto;
}

.upload-demo {
  width: 100%;
}

.upload-demo .el-upload {
  width: 100%;
}

.upload-demo .el-upload-dragger {
  width: 100%;
  height: 200px;
}
</style>
