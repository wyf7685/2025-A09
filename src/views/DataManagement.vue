<script setup lang="ts">
import DataSourceHeader from '@/components/data/DataSourceHeader.vue';
import DataSourceSearchBar from '@/components/data/DataSourceSearchBar.vue';
import DataSourceTable from '@/components/data/DataSourceTable.vue';
import EditDataSourceDialog from '@/components/data/EditDataSourceDialog.vue';
import PreviewDataDialog from '@/components/data/PreviewDataDialog.vue';
import { useDataSourceStore } from '@/stores/datasource';
import { useModelStore } from '@/stores/model';
import { useSessionStore } from '@/stores/session';
import type { DataSourceMetadataWithID } from '@/types';
import type { CleaningAction, CleaningSuggestion, DataQualityReport } from '@/types/cleaning';
import type { ElTable } from 'element-plus';
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();
const modelStore = useModelStore();

// =============================================
// 数据源列表状态
// =============================================
const datasources = ref<DataSourceMetadataWithID[]>([]);
const filteredDataSources = ref<DataSourceMetadataWithID[]>([]);
const paginatedDataSources = ref<DataSourceMetadataWithID[]>([]);
const isLoading = ref(false);
const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = ref(10);

// =============================================
// 对话框相关状态
// =============================================
const editDialogVisible = ref(false);
const previewDialogVisible = ref(false);
const addDatabaseDialogVisible = ref(false);
const currentEditSource = ref<DataSourceMetadataWithID | null>(null);

// =============================================
// 预览数据状态
// =============================================
const previewData = ref<any[]>([]);
const previewColumns = ref<string[]>([]);
const previewLoading = ref(false);
const previewPagination = ref({
  current: 1,
  pageSize: 10,
  total: 0
});

// =============================================
// 数据清洗弹窗相关状态
// =============================================
const dataCleaningDialogVisible = ref(false);
const currentUploadFile = ref<File | null>(null);
const dataQualityReport = ref<DataQualityReport | null>(null);
const cleaningSuggestions = ref<CleaningSuggestion[]>([]);
const fieldMappings = ref<Record<string, string>>({});
const isAnalyzing = ref(false);
const isCleaning = ref(false);
const fileMetadata = ref({
  name: '',
  description: ''
});
const userRequirements = ref('');
const selectedCleaningActions = ref<CleaningAction[]>([]);
const cleaningStep = ref<'upload' | 'analysis' | 'cleaning' | 'complete'>('upload');
const analysisResult = ref<any>(null);

// =============================================
// 智能分析相关状态
// =============================================
const isSmartAnalyzing = ref(false);
const showAdvancedOptions = ref(false);
const selectedModel = ref('');
const availableModels = ref([
  { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (推荐)' },
  { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
  { value: 'gpt-4', label: 'GPT-4' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
]);

// 获取可用模型列表
const fetchAvailableModels = async () => {
  try {
    await modelStore.fetchAvailableModels();
    // 将store中的模型转换为组件需要的格式
    availableModels.value = modelStore.availableModels.map(model => ({
      value: model.id,
      label: `${model.name} (${model.provider})`
    }));

    // 设置默认选中的模型
    if (availableModels.value.length > 0) {
      selectedModel.value = availableModels.value[0].value;
    }
  } catch (error) {
    console.error('获取可用模型失败:', error);
  }
};

// =============================================
// 多选相关状态
// =============================================
const selectedSources = ref<string[]>([]);
const tableRef = ref<InstanceType<typeof ElTable>>();

// =============================================
// 数据源列表相关方法
// =============================================

// 刷新数据集列表
const fetchDatasets = async () => {
  isLoading.value = true;
  try {
    const sources = await dataSourceStore.listDataSources();
    datasources.value = sources;
    updateFilteredDataSources();
  } catch (error) {
    ElMessage.error('获取数据源列表失败');
    console.error(error);
  } finally {
    isLoading.value = false;
  }
};

// 更新过滤后的数据源
const updateFilteredDataSources = () => {
  let filtered = datasources.value;

  if (searchQuery.value) {
    filtered = filtered.filter(ds =>
      ds.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      ds.description?.toLowerCase().includes(searchQuery.value.toLowerCase())
    );
  }

  filteredDataSources.value = filtered;
  updatePaginatedDataSources();
};

// 更新分页数据
const updatePaginatedDataSources = () => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  paginatedDataSources.value = filteredDataSources.value.slice(start, end);
};

// 获取数据源名称映射（用于选择展示）
const getDatasourceNameMap = (): Record<string, string> => {
  const nameMap: Record<string, string> = {};
  datasources.value.forEach(ds => {
    nameMap[ds.source_id] = ds.name;
  });
  return nameMap;
};


// =============================================
// 数据源操作方法
// =============================================

// 选择数据集进行分析
const selectForAnalysis = async (metadata: DataSourceMetadataWithID) => {
  try {
    const session = await sessionStore.createSession([metadata.source_id]);
    sessionStore.setCurrentSession(session);
    ElMessage.success(`已选择数据集 "${metadata.name.slice(0, 8)}..." 进行分析`);
    router.push('/chat-analysis');
  } catch (error) {
    console.error('创建会话失败:', error);
    ElMessage.error('创建会话失败');
  }
};

// 编辑数据源
const openEditDialog = (source: DataSourceMetadataWithID) => {
  currentEditSource.value = source;
  editDialogVisible.value = true;
};

// 保存编辑
const saveEdit = async (name: string, description: string) => {
  if (!currentEditSource.value) return;

  try {
    await dataSourceStore.updateDataSource(currentEditSource.value.source_id, {
      name,
      description
    });
    ElMessage.success('数据源信息更新成功');
    editDialogVisible.value = false;
    await fetchDatasets();
  } catch (error) {
    ElMessage.error('更新失败');
    console.error(error);
  }
};

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
    );

    await dataSourceStore.deleteDataSource(source.source_id);
    ElMessage.success('数据源删除成功');
    await fetchDatasets();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败');
      console.error(error);
    }
  }
};

// =============================================
// 预览数据相关方法
// =============================================

// 打开预览对话框
const openPreviewDialog = async (source: DataSourceMetadataWithID) => {
  currentEditSource.value = source;
  previewDialogVisible.value = true;
  await loadPreviewData(1);
};

// 加载预览数据
const loadPreviewData = async (page: number = 1) => {
  if (!currentEditSource.value) return;

  previewLoading.value = true;
  try {
    const skip = (page - 1) * previewPagination.value.pageSize;
    const result = await dataSourceStore.getSourceData(
      currentEditSource.value.source_id,
      skip,
      previewPagination.value.pageSize
    );

    previewData.value = result.data;
    previewPagination.value.total = result.total;
    previewPagination.value.current = page;

    if (result.data.length > 0) {
      previewColumns.value = Object.keys(result.data[0]);
    }
  } catch (error) {
    ElMessage.error('加载预览数据失败');
    console.error(error);
  } finally {
    previewLoading.value = false;
  }
};

// =============================================
// 多选相关方法
// =============================================

// 处理表格选择变化
const handleSelectionChange = (selection: DataSourceMetadataWithID[]) => {
  selectedSources.value = selection.map(item => item.source_id);
};

// 使用选中的数据源创建会话
const createSessionWithSelectedSources = async () => {
  if (selectedSources.value.length === 0) {
    ElMessage.warning('请至少选择一个数据集');
    return;
  }

  try {
    const session = await sessionStore.createSession(selectedSources.value);
    sessionStore.setCurrentSession(session);

    const message = selectedSources.value.length === 1
      ? '新对话创建成功'
      : `成功创建包含 ${selectedSources.value.length} 个数据集的对话`;

    ElMessage.success(message);

    // 导航到分析页面
    router.push('/chat-analysis');
  } catch (error) {
    console.error('创建会话失败:', error);
    ElMessage.error('创建会话失败');
  }
};

// =============================================
// 生命周期和监听
// =============================================

onMounted(() => {
  fetchDatasets();
  fetchAvailableModels(); // 在组件挂载时获取可用模型
});

// 监听搜索查询变化，更新过滤结果
watch(searchQuery, updateFilteredDataSources);

// 监听数据源变化，更新过滤结果
watch(datasources, updateFilteredDataSources, { deep: true });

// 监听页码和页面大小变化，更新分页数据
watch([currentPage, pageSize], updatePaginatedDataSources);
</script>

<template>
  <div class="data-management-container">
    <!-- 顶部操作区域 -->
    <DataSourceHeader :isLoading="isLoading" @refresh="fetchDatasets" />

    <!-- 搜索和过滤区域 -->
    <DataSourceSearchBar v-model:searchQuery="searchQuery" :selectedSources="selectedSources"
      :sourceNames="getDatasourceNameMap()" @createSession="createSessionWithSelectedSources" />

    <!-- 数据源表格 -->
    <DataSourceTable :dataSources="paginatedDataSources" :isLoading="isLoading" v-model:currentPage="currentPage"
      v-model:pageSize="pageSize" :total="filteredDataSources.length" :selectedSources="selectedSources"
      @selectionChange="handleSelectionChange" @edit="openEditDialog" @delete="deleteDataSource"
      @preview="openPreviewDialog" @analyze="selectForAnalysis" />

    <!-- 编辑数据源对话框 -->
    <EditDataSourceDialog v-model:visible="editDialogVisible" :datasource="currentEditSource" @save="saveEdit" />

    <!-- 预览数据对话框 -->
    <PreviewDataDialog v-model:visible="previewDialogVisible" :datasource="currentEditSource" :previewData="previewData"
      :previewColumns="previewColumns" :pagination="previewPagination" :loading="previewLoading"
      @loadPage="loadPreviewData" />
  </div>
</template>

<style lang="scss" scoped>
.data-management-container {
  padding: 24px;
  background: #f8fafc;
  min-height: 100vh;
}
</style>
