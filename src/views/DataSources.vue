<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { useRouter } from 'vue-router'
import type { DataSource, ConfigFormData, DatasetResponse } from '@/types';


const router = useRouter()
const appStore = useAppStore()

// 响应式数据
const loading = ref<boolean>(false)
const loadingSource = ref<string>('')
const searchKeyword = ref<string>('')
const dremioSources = ref<DataSource[]>([])
const configDialogVisible = ref<boolean>(false)
const configForm = ref<ConfigFormData>({
  name: '',
  type: '',
  host: '',
  port: '',
  database: '',
  username: '',
  password: ''
})

// 计算属性
const filteredSources = computed<DataSource[]>(() => {
  if (!searchKeyword.value) return dremioSources.value

  return dremioSources.value.filter(source =>
    source.name.toLowerCase().includes(searchKeyword.value.toLowerCase()) ||
    (source.description && source.description.toLowerCase().includes(searchKeyword.value.toLowerCase()))
  )
})

// 方法
const loadDremioSources = async (): Promise<void> => {
  loading.value = true
  try {
    const response = await appStore.getDremioSources()

    // 模拟数据源信息（因为实际API可能返回简单列表）
    dremioSources.value = (response.sources || []).map((source: string | { name: string }) => ({
      name: typeof source === 'string' ? source : source.name,
      type: 'Dremio',
      description: `Dremio 数据源: ${typeof source === 'string' ? source : source.name}`,
      status: 'connected' as const // 假设已连接
    }))

    ElMessage.success('数据源列表已刷新')
  } catch (error) {
    console.error('加载数据源失败:', error)
    // 如果后端不可用，显示示例数据
    dremioSources.value = [
      {
        name: 'sample_database',
        type: 'Dremio',
        description: '示例数据库（后端服务不可用时的演示数据）',
        status: 'disconnected' as const
      }
    ]
  } finally {
    loading.value = false
  }
}

const loadFromSource = async (source: DataSource): Promise<void> => {
  try {
    await ElMessageBox.confirm(
      `确定要从数据源 "${source.name}" 加载数据吗？`,
      '确认加载',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )

    loadingSource.value = source.name

    const response = await appStore.loadDremioData(
      source.name,
      appStore.currentSessionId
    ) as DatasetResponse

    ElMessage.success('数据加载成功！')

    // 设置为当前数据集
    appStore.setCurrentDataset({
      id: response.dataset_id,
      name: source.name,
      source_type: 'dremio',
      created_at: new Date().toISOString(),
      // overview: response.overview
    })

    // 跳转到工作台查看数据
    try {
      await ElMessageBox.confirm(
        '数据已成功加载，是否跳转到工作台查看？',
        '加载完成',
        {
          confirmButtonText: '查看数据',
          cancelButtonText: '留在此页',
          type: 'success'
        }
      )

      router.push('/dashboard')
    } catch {
      // 用户选择留在当前页面
    }

  } catch (error) {
    if (error !== 'cancel') {
      console.error('加载数据失败:', error)
    }
  } finally {
    loadingSource.value = ''
  }
}

const testConnection = async (source: DataSource): Promise<void> => {
  ElMessage.info(`正在测试连接到 ${source.name}...`)

  // 模拟连接测试
  setTimeout(() => {
    if (source.status === 'connected') {
      ElMessage.success(`连接到 ${source.name} 成功！`)
    } else {
      ElMessage.error(`连接到 ${source.name} 失败，请检查配置`)
    }
  }, 1500)
}

const addDataSource = (): void => {
  configForm.value = {
    name: '',
    type: '',
    host: '',
    port: '',
    database: '',
    username: '',
    password: ''
  }
  configDialogVisible.value = true
}

const saveDataSource = (): void => {
  ElMessage.info('数据源配置功能将在后续版本中支持')
  configDialogVisible.value = false
}

// 生命周期
onMounted(() => {
  loadDremioSources()
})
</script>

<template>
  <div class="data-sources">
    <div class="analysis-card">
      <h2 style="margin-bottom: 20px;">
        <el-icon style="margin-right: 8px;">
          <Database />
        </el-icon>
        数据源管理
      </h2>

      <!-- Dremio 数据源 -->
      <div style="margin-bottom: 32px;">
        <h3 style="margin-bottom: 16px;">Dremio 数据源</h3>

        <div class="toolbar">
          <el-button type="primary" @click="loadDremioSources" :loading="loading">
            <el-icon>
              <Refresh />
            </el-icon>
            刷新数据源
          </el-button>
          <el-input v-model="searchKeyword" placeholder="搜索数据源..." style="width: 300px;" clearable>
            <template #prefix>
              <el-icon>
                <Search />
              </el-icon>
            </template>
          </el-input>
        </div>

        <!-- 数据源列表 -->
        <el-table :data="filteredSources" style="width: 100%" v-loading="loading" empty-text="暂无数据源">
          <el-table-column prop="name" label="数据源名称" />
          <el-table-column prop="type" label="类型" />
          <el-table-column prop="description" label="描述" />
          <el-table-column prop="status" label="状态">
            <template #default="scope">
              <el-tag :type="scope.row.status === 'connected' ? 'success' : 'danger'">
                {{ scope.row.status === 'connected' ? '已连接' : '未连接' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="scope">
              <el-button size="small" @click="loadFromSource(scope.row)" :loading="loadingSource === scope.row.name">
                加载数据
              </el-button>
              <el-button size="small" @click="testConnection(scope.row)">
                测试连接
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 其他数据源类型 -->
      <div>
        <h3 style="margin-bottom: 16px;">其他数据源</h3>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-card class="data-source-card">
              <div style="text-align: center;">
                <el-icon style="font-size: 48px; color: #409EFF; margin-bottom: 12px;">
                  <Document />
                </el-icon>
                <h4>CSV/Excel 文件</h4>
                <p style="color: #666; margin: 12px 0;">从本地文件系统上传数据</p>
                <el-button type="primary" @click="$router.push('/data-upload')">
                  上传文件
                </el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :span="8">
            <el-card class="data-source-card">
              <div style="text-align: center;">
                <el-icon style="font-size: 48px; color: #67C23A; margin-bottom: 12px;">
                  <Connection />
                </el-icon>
                <h4>MySQL 数据库</h4>
                <p style="color: #666; margin: 12px 0;">连接到 MySQL 数据库</p>
                <el-button disabled>即将支持</el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :span="8">
            <el-card class="data-source-card">
              <div style="text-align: center;">
                <el-icon style="font-size: 48px; color: #E6A23C; margin-bottom: 12px;">
                  <Coin />
                </el-icon>
                <h4>PostgreSQL</h4>
                <p style="color: #666; margin: 12px 0;">连接到 PostgreSQL 数据库</p>
                <el-button disabled>即将支持</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </div>

    <!-- 数据源配置对话框 -->
    <el-dialog v-model="configDialogVisible" title="数据源配置" width="50%">
      <el-form :model="configForm" label-width="120px">
        <el-form-item label="数据源名称">
          <el-input v-model="configForm.name" />
        </el-form-item>
        <el-form-item label="连接类型">
          <el-select v-model="configForm.type" placeholder="请选择">
            <el-option label="MySQL" value="mysql" />
            <el-option label="PostgreSQL" value="postgresql" />
            <el-option label="Dremio" value="dremio" />
          </el-select>
        </el-form-item>
        <el-form-item label="主机地址">
          <el-input v-model="configForm.host" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input v-model="configForm.port" type="number" />
        </el-form-item>
        <el-form-item label="数据库名">
          <el-input v-model="configForm.database" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="configForm.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="configForm.password" type="password" />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="configDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveDataSource">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.data-sources {
  max-width: 1200px;
  margin: 0 auto;
}

.data-source-card {
  height: 200px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.data-source-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.data-source-card .el-card__body {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
