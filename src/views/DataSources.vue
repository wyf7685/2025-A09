<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { useRouter } from 'vue-router';
import { useDataSourceStore } from '@/stores/datasource';
import { useSessionStore } from '@/stores/session';
import type { DataSourceMetadata, DremioSource } from '@/types';

type MetadataWithSourceId = DataSourceMetadata & { source_id: string }

const router = useRouter();
const dataSourceStore = useDataSourceStore();
const sessionStore = useSessionStore();

// 响应式数据
const loading = ref<boolean>(false);
const searchKeyword = ref<string>('');
const dataSources = ref<MetadataWithSourceId[]>([]);

// 文件上传相关
const fileUploadDialogVisible = ref<boolean>(false);
const fileUploadLoading = ref<boolean>(false);
const selectedFile = ref<File | null>(null);
const fileUploadForm = ref({
  name: '',
  description: ''
});

// 数据库连接相关
const dbConnectionDialogVisible = ref<boolean>(false);
const dbConnectionLoading = ref<boolean>(false);
const dbConnectionForm = ref({
  name: '',
  description: '',
  type: 'postgres',
  host: '',
  port: 5432,
  database: '',
  username: '',
  password: ''
});

// Dremio连接相关
const dremioDialogVisible = ref<boolean>(false);
const dremioLoading = ref<boolean>(false);
const dremioForm = ref({
  name: '',
  description: '',
  path: '',
});

// 数据源编辑相关
const editDialogVisible = ref<boolean>(false);
const editingSource = ref<MetadataWithSourceId | null>(null);
const editForm = ref({
  name: '',
  description: ''
});

// 数据预览相关
const previewDialogVisible = ref<boolean>(false);
const previewData = ref<any[]>([]);
const previewLoading = ref<boolean>(false);
const previewSource = ref<MetadataWithSourceId | null>(null);

// 计算属性
const filteredSources = computed(() => {
  if (!searchKeyword.value) return dataSources.value;

  const keyword = searchKeyword.value.toLowerCase();
  return dataSources.value.filter(source =>
    source.name.toLowerCase().includes(keyword) ||
    (source.description && source.description.toLowerCase().includes(keyword))
  );
});

// 方法
const loadDataSources = async () => {
  loading.value = true;
  try {
    const sources = await dataSourceStore.listDataSources();
    dataSources.value = sources;
  } catch (error) {
    console.error('加载数据源失败:', error);
    ElMessage.error('加载数据源列表失败');
  } finally {
    loading.value = false;
  }
};

// 文件上传相关方法
const openFileUploadDialog = () => {
  selectedFile.value = null;
  fileUploadForm.value = { name: '', description: '' };
  fileUploadDialogVisible.value = true;
};

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0];
    // 默认使用文件名作为数据源名称
    fileUploadForm.value.name = selectedFile.value.name;
  }
};

const uploadFile = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择要上传的文件');
    return;
  }

  fileUploadLoading.value = true;
  try {
    const result = await dataSourceStore.uploadCsvSource(
      selectedFile.value,
      fileUploadForm.value.name
    );

    // 更新元数据描述
    if (fileUploadForm.value.description) {
      // 假设后端支持更新描述的API
      // await dataSourceStore.updateDataSource(result.source_id, {
      //   description: fileUploadForm.value.description
      // });
    }

    ElMessage.success('文件上传成功');
    fileUploadDialogVisible.value = false;
    await loadDataSources();
  } catch (error) {
    console.error('上传文件失败:', error);
    ElMessage.error('上传文件失败');
  } finally {
    fileUploadLoading.value = false;
  }
};

// 数据库连接相关方法
const openDbConnectionDialog = () => {
  dbConnectionForm.value = {
    name: '',
    description: '',
    type: 'postgres',
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: ''
  };
  dbConnectionDialogVisible.value = true;
};

const saveDbConnection = async () => {
  if (!dbConnectionForm.value.name || !dbConnectionForm.value.host) {
    ElMessage.warning('请填写必要的连接信息');
    return;
  }

  dbConnectionLoading.value = true;
  try {
    ElMessage.info('数据库连接功能将在后续版本中支持');
    // 这里应该调用创建数据库连接的API
    // await dataSourceStore.createDatabaseConnection({...dbConnectionForm.value});

    dbConnectionDialogVisible.value = false;
    await loadDataSources();
  } catch (error) {
    console.error('创建数据库连接失败:', error);
    ElMessage.error('创建数据库连接失败');
  } finally {
    dbConnectionLoading.value = false;
  }
};

// Dremio连接相关方法
const openDremioDialog = () => {
  dremioForm.value = {
    name: '',
    description: '',
    path: '',
  };
  dremioDialogVisible.value = true;
};

const saveDremioConnection = async () => {
  if (!dremioForm.value.name || !dremioForm.value.path) {
    ElMessage.warning('请填写Dremio路径信息');
    return;
  }

  dremioLoading.value = true;
  try {
    const source: DremioSource = {
      path: dremioForm.value.path.split('.'),
      type: 'DATASET',
      name: dremioForm.value.name,
      description: dremioForm.value.description
    };

    await dataSourceStore.registerDremioSource(source);
    ElMessage.success('Dremio数据源添加成功');

    dremioDialogVisible.value = false;
    await loadDataSources();
  } catch (error) {
    console.error('添加Dremio数据源失败:', error);
    ElMessage.error('添加Dremio数据源失败');
  } finally {
    dremioLoading.value = false;
  }
};

// 编辑数据源
const openEditDialog = (source: MetadataWithSourceId) => {
  editingSource.value = source;
  editForm.value = {
    name: source.name,
    description: source.description || ''
  };
  editDialogVisible.value = true;
};

const saveSourceEdit = async () => {
  if (!editingSource.value) return;

  try {
    // 假设后端支持更新数据源元数据的API
    // await dataSourceStore.updateDataSource(editingSource.value.id, {
    //   name: editForm.value.name,
    //   description: editForm.value.description
    // });

    ElMessage.info('数据源编辑功能将在后续版本中支持');
    editDialogVisible.value = false;
    await loadDataSources();
  } catch (error) {
    console.error('更新数据源失败:', error);
    ElMessage.error('更新数据源失败');
  }
};

// 预览数据
const previewDataSource = async (source: MetadataWithSourceId) => {
  previewLoading.value = true;
  previewSource.value = source;
  previewDialogVisible.value = true;

  try {
    const result = await dataSourceStore.getSourceData(source.source_id, 0, 10);
    previewData.value = result.data;
  } catch (error) {
    console.error('获取数据源预览失败:', error);
    ElMessage.error('获取数据预览失败');
  } finally {
    previewLoading.value = false;
  }
};

// 创建会话并使用数据源
const createSessionWithDataSource = async (source: MetadataWithSourceId) => {
  try {
    await ElMessageBox.confirm(
      `确定要创建新会话并使用 "${source.name}" 数据源吗？`,
      '创建会话',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    );

    const session = await sessionStore.createSession(source.source_id);
    sessionStore.setCurrentSession(session);

    ElMessage.success('会话创建成功');
    router.push('/chat-analysis');
  } catch (error) {
    if (error !== 'cancel') {
      console.error('创建会话失败:', error);
      ElMessage.error('创建会话失败');
    }
  }
};

// 删除数据源
const deleteSource = async (source: MetadataWithSourceId) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除数据源 "${source.name}" 吗？这将同时删除使用此数据源的所有会话。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    await dataSourceStore.deleteDataSource(source.source_id);
    ElMessage.success('数据源已删除');
    await loadDataSources();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除数据源失败:', error);
      ElMessage.error('删除数据源失败');
    }
  }
};

// 生命周期
onMounted(() => {
  loadDataSources();
});
</script>

<template>
  <div class="data-sources">
    <div class="data-sources-header">
      <h1>数据源管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="loadDataSources" :loading="loading">
          <el-icon>
            <Refresh />
          </el-icon>
          刷新
        </el-button>
        <el-input v-model="searchKeyword" placeholder="搜索数据源..." style="width: 300px; margin: 0 16px;" clearable>
          <template #prefix>
            <el-icon>
              <Search />
            </el-icon>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 添加数据源卡片行 -->
    <div class="data-source-cards">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card class="add-source-card" @click="openFileUploadDialog">
            <div class="card-content">
              <el-icon class="icon">
                <Upload />
              </el-icon>
              <h3>上传 CSV/Excel</h3>
              <p>从本地文件系统导入数据</p>
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card class="add-source-card" @click="openDbConnectionDialog">
            <div class="card-content">
              <el-icon class="icon">
                <Connection />
              </el-icon>
              <h3>添加数据库连接</h3>
              <p>连接到外部数据库</p>
            </div>
          </el-card>
        </el-col>
        <!-- <el-col :span="8">
          <el-card class="add-source-card" @click="openDremioDialog">
            <div class="card-content">
              <el-icon class="icon">
                <DataBoard />
              </el-icon>
              <h3>添加Dremio数据源</h3>
              <p>连接到Dremio数据源</p>
            </div>
          </el-card>
        </el-col> -->
      </el-row>
    </div>

    <!-- 数据源列表 -->
    <div class="data-sources-list">
      <h2>数据源列表</h2>
      <el-table :data="filteredSources" style="width: 100%" v-loading="loading" row-key="id">
        <el-table-column prop="id" label="ID" width="100" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="source_type" label="类型">
          <template #default="{ row }">
            <el-tag :type="getSourceTypeTag(row.source_type)">
              {{ formatSourceType(row.source_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button size="small" @click="previewDataSource(row)" type="info">
              预览
            </el-button>
            <el-button size="small" @click="openEditDialog(row)">
              编辑
            </el-button>
            <el-button size="small" type="primary" @click="createSessionWithDataSource(row)">
              使用
            </el-button>
            <el-button size="small" type="danger" @click="deleteSource(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="empty-state" v-if="!loading && filteredSources.length === 0">
        <el-empty description="暂无数据源，请添加数据源" />
      </div>
    </div>

    <!-- 文件上传对话框 -->
    <el-dialog v-model="fileUploadDialogVisible" title="上传CSV/Excel文件" width="500px" destroy-on-close>
      <el-form :model="fileUploadForm" label-width="80px">
        <el-form-item label="文件">
          <input type="file" @change="handleFileChange" accept=".csv,.xlsx,.xls" class="file-input" />
          <div class="selected-file" v-if="selectedFile">
            已选择: {{ selectedFile.name }} ({{ formatFileSize(selectedFile.size) }})
          </div>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="fileUploadForm.name" placeholder="数据源名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="fileUploadForm.description" type="textarea" placeholder="数据源描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fileUploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="uploadFile" :loading="fileUploadLoading">
          上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 数据库连接对话框 -->
    <el-dialog v-model="dbConnectionDialogVisible" title="添加数据库连接" width="500px">
      <el-form :model="dbConnectionForm" label-width="120px">
        <el-form-item label="连接名称" required>
          <el-input v-model="dbConnectionForm.name" placeholder="数据库连接名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="dbConnectionForm.description" type="textarea" placeholder="连接描述（可选）" />
        </el-form-item>
        <el-form-item label="数据库类型" required>
          <el-select v-model="dbConnectionForm.type" style="width: 100%">
            <el-option label="PostgreSQL" value="postgres" />
            <el-option label="MySQL" value="mysql" disabled />
            <el-option label="SQLite" value="sqlite" disabled />
          </el-select>
        </el-form-item>
        <el-form-item label="主机地址" required>
          <el-input v-model="dbConnectionForm.host" placeholder="例如：localhost" />
        </el-form-item>
        <el-form-item label="端口" required>
          <el-input-number v-model="dbConnectionForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="数据库名" required>
          <el-input v-model="dbConnectionForm.database" />
        </el-form-item>
        <el-form-item label="用户名" required>
          <el-input v-model="dbConnectionForm.username" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="dbConnectionForm.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dbConnectionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDbConnection" :loading="dbConnectionLoading">
          连接
        </el-button>
      </template>
    </el-dialog>

    <!-- Dremio连接对话框 -->
    <el-dialog v-model="dremioDialogVisible" title="添加Dremio数据源" width="500px">
      <el-form :model="dremioForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="dremioForm.name" placeholder="数据源名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="dremioForm.description" type="textarea" placeholder="数据源描述（可选）" />
        </el-form-item>
        <el-form-item label="路径" required>
          <el-input v-model="dremioForm.path" placeholder="例如：space.folder.table" />
          <div class="form-help-text">使用点(.)分隔路径组件</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dremioDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveDremioConnection" :loading="dremioLoading">
          添加
        </el-button>
      </template>
    </el-dialog>

    <!-- 数据源编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑数据源" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSourceEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 数据预览对话框 -->
    <el-dialog v-model="previewDialogVisible" :title="`数据预览: ${previewSource?.name || '未命名'}`" width="80%">
      <div v-loading="previewLoading">
        <div v-if="previewData.length > 0" class="preview-container">
          <el-table :data="previewData" border style="width: 100%">
            <el-table-column v-for="column in Object.keys(previewData[0])" :key="column" :prop="column" :label="column"
              min-width="150" />
          </el-table>
          <div class="preview-note">
            显示前10条记录，共{{ previewSource?.row_count || '未知' }}条
          </div>
        </div>
        <el-empty v-else description="无预览数据" />
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="createSessionWithDataSource(previewSource!)">
          使用此数据源
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.data-sources {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.data-sources-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.data-source-cards {
  margin-bottom: 40px;
}

.add-source-card {
  height: 180px;
  cursor: pointer;
  transition: all 0.3s;
}

.add-source-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
}

.card-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
}

.card-content .icon {
  font-size: 48px;
  margin-bottom: 16px;
  color: var(--el-color-primary);
}

.card-content h3 {
  margin: 0 0 8px;
}

.card-content p {
  margin: 0;
  color: #666;
}

.data-sources-list {
  margin-top: 20px;
}

.file-input {
  display: block;
  margin-bottom: 10px;
}

.selected-file {
  margin-top: 5px;
  font-size: 0.9em;
  color: #666;
}

.preview-container {
  max-height: 500px;
  overflow: auto;
}

.preview-note {
  margin-top: 10px;
  font-size: 0.9em;
  color: #666;
  text-align: right;
}

.form-help-text {
  font-size: 0.85em;
  color: #666;
  margin-top: 4px;
}

.empty-state {
  padding: 40px 0;
}
</style>

<script lang="ts">
// 辅助函数
function formatDate(dateString: string) {
  const date = new Date(dateString);
  return date.toLocaleString();
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function getSourceTypeTag(sourceType: string) {
  const typeMap = {
    csv: 'success',
    excel: 'success',
    dremio: 'primary',
    postgres: 'warning',
    mysql: 'warning',
    sqlite: 'info',
    dataframe: 'danger',
    memory: 'danger'
  };
  return typeMap[sourceType.toLowerCase() as keyof typeof typeMap] || 'info';
}

function formatSourceType(sourceType: string) {
  const typeMap = {
    csv: 'CSV文件',
    excel: 'Excel文件',
    dremio: 'Dremio',
    postgres: 'PostgreSQL',
    mysql: 'MySQL',
    sqlite: 'SQLite',
    dataframe: '内存数据',
    memory: '内存数据'
  };
  return typeMap[sourceType.toLowerCase() as keyof typeof typeMap] || sourceType;
}
</script>
