<script setup lang="ts">
import AddDatabaseDialog from '@/components/AddDatabaseDialog.vue';
import DataCleaningDialog from '@/components/data/DataCleaningDialog.vue';
import DataSourceHeader from '@/components/data/DataSourceHeader.vue';
import DataSourceSearchBar from '@/components/data/DataSourceSearchBar.vue';
import DataSourceTable from '@/components/data/DataSourceTable.vue';
import DataSourceUploadPanel from '@/components/data/DataSourceUploadPanel.vue';
import EditDataSourceDialog from '@/components/data/EditDataSourceDialog.vue';
import PreviewDataDialog from '@/components/data/PreviewDataDialog.vue';
import { useDataSourceStore } from '@/stores/datasource';
import { useSessionStore } from '@/stores/session';
import type { DataSourceMetadataWithID } from '@/types';
import type { CleaningAction, CleaningSuggestion, DataQualityReport } from '@/types/cleaning';
import { cleaningAPI, dataSourceAPI } from '@/utils/api';
import type { ElTable } from 'element-plus';
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const sessionStore = useSessionStore();
const dataSourceStore = useDataSourceStore();

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
// 文件上传与数据库连接相关方法
// =============================================

// 处理文件上传
const handleFileUpload = async (options: { file: File; }) => {
  const file = options.file;
  if (!file) return;

  // 存储文件信息并显示清洗弹窗
  currentUploadFile.value = file;
  fileMetadata.value.name = file.name.replace(/\.[^/.]+$/, ''); // 移除文件扩展名
  fileMetadata.value.description = '';
  userRequirements.value = '';
  selectedModel.value = availableModels.value[0].value;
  dataCleaningDialogVisible.value = true;
  cleaningStep.value = 'upload';

  // 重置状态
  dataQualityReport.value = null;
  cleaningSuggestions.value = [];
  fieldMappings.value = {};
  selectedCleaningActions.value = [];
  analysisResult.value = null;
};

// 打开添加数据库对话框
const openAddDatabase = () => {
  addDatabaseDialogVisible.value = true;
};

// 添加数据库成功回调
const onDatabaseAddSuccess = async () => {
  ElMessage.success('数据库连接添加成功');
  await fetchDatasets(); // 刷新数据源列表
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
// 数据清洗相关方法
// =============================================

// 智能数据质量分析
const analyzeDataQualityWithAI = async () => {
  if (!currentUploadFile.value) return;

  isSmartAnalyzing.value = true;
  cleaningStep.value = 'analysis';

  try {
    // 使用智能Agent API
    const result = await cleaningAPI.analyzeDataQuality(
      currentUploadFile.value,
      userRequirements.value || undefined,
      selectedModel.value || undefined
    );

    if (result.success) {
      analysisResult.value = result;
      dataQualityReport.value = result.quality_report || null;
      cleaningSuggestions.value = result.cleaning_suggestions || [];
      fieldMappings.value = result.field_mappings || {};

      // 记录字段映射信息，等待用户选择操作
      if (result.field_mappings_applied && result.cleaned_file_path) {
        ElMessage.info('字段映射已准备完成，您可以选择直接上传或执行清洗操作');
      }

      ElMessage.success('智能数据质量分析完成！');
    } else {
      throw new Error(result.error || '分析失败');
    }
  } catch (error) {
    ElMessage.error('智能数据质量分析失败');
    console.error(error);
    cleaningStep.value = 'upload';
  } finally {
    isSmartAnalyzing.value = false;
  }
};

// 应用清洗动作
const applyCleaningActions = async () => {
  if (selectedCleaningActions.value.length === 0) {
    ElMessage.warning('请选择至少一个清洗建议');
    return;
  }

  isCleaning.value = true;
  try {
    // 确保当前文件存在
    if (!currentUploadFile.value) {
      throw new Error('当前文件不存在');
    }

    // 准备清洗建议，确保格式正确
    const preparedSuggestions = selectedCleaningActions.value.map((action: any) => {
      // 从原始建议中获取更多信息
      const originalSuggestion = cleaningSuggestions.value.find((s: any) =>
        s.type === action.type && s.column === action.column
      );

      return {
        title: originalSuggestion?.title || `清洗操作: ${action.type}`,
        type: action.type,
        column: action.column || '',
        description: originalSuggestion?.description || `应用清洗操作: ${action.type} on ${action.column}`,
        severity: originalSuggestion?.severity || 'medium',
        priority: originalSuggestion?.priority || 'medium',
        options: originalSuggestion?.options || [{
          method: action.parameters || 'default',
          description: `清洗列 ${action.column}`
        }],
        suggested_action: originalSuggestion?.description || `清洗列 ${action.column}`,
        parameters: { method: action.parameters }
      };
    });

    // 执行清洗操作
    const cleaningResult = await cleaningAPI.executeCleaning(
      currentUploadFile.value,
      preparedSuggestions as any,
      fieldMappings.value,
      userRequirements.value,
      selectedModel.value
    );

    if (cleaningResult.success) {
      ElMessage.success(`清洗操作执行成功！应用了 ${cleaningResult.applied_operations.length} 个清洗操作`);

      // 保存清洗结果
      analysisResult.value = {
        ...analysisResult.value,
        cleaning_result: cleaningResult,
        cleaned_file_path: cleaningResult.cleaned_file_path,
        cleaned_data_info: cleaningResult.cleaned_data_info
      };

      // 执行清洗后，自动上传清洗后的数据到Dremio
      try {
        ElMessage.info('正在上传清洗后的数据到Dremio...');

        const uploadResult = await dataSourceAPI.uploadFile(
          currentUploadFile.value,
          fileMetadata.value.name,
          fileMetadata.value.description,
          cleaningResult.cleaned_file_path,
          fieldMappings.value,
          true  // 标记为清洗后的数据
        );

        ElMessage.success('清洗后的数据已成功上传到Dremio！');

        // 标记数据已上传
        analysisResult.value.data_uploaded = true;
        analysisResult.value.upload_result = uploadResult;

        // 上传成功后刷新数据源列表
        await fetchDatasets();
        ElMessage.success('数据源列表已更新');

        cleaningStep.value = 'complete';
      } catch (uploadError: any) {
        ElMessage.error('清洗操作成功，但上传到Dremio失败: ' + (uploadError?.message || uploadError));
        console.error('上传清洗后数据失败:', uploadError);
        cleaningStep.value = 'complete';
      }
    } else {
      throw new Error(cleaningResult.error || '清洗执行失败');
    }
  } catch (error: any) {
    ElMessage.error('清洗操作执行失败: ' + (error?.message || error));
    console.error('清洗操作详细错误:', error);
  } finally {
    isCleaning.value = false;
  }
};

// 跳过清洗直接上传
const skipCleaningAndUpload = async () => {
  if (!currentUploadFile.value) return;

  isLoading.value = true;
  try {
    const mappedFilePath = analysisResult.value?.cleaned_file_path;
    const fieldMappingsToApply = analysisResult.value?.field_mappings || fieldMappings.value;

    if (mappedFilePath && Object.keys(fieldMappingsToApply).length > 0) {
      // 使用应用了字段映射的文件
      await dataSourceAPI.uploadFile(
        currentUploadFile.value,
        fileMetadata.value.name,
        fileMetadata.value.description,
        mappedFilePath,
        fieldMappingsToApply,
        true  // 标记为已处理的数据
      );
      ElMessage.success('字段映射已应用，数据上传成功！');
    } else {
      // 没有字段映射，使用原始文件
      await dataSourceStore.uploadFileSource(
        currentUploadFile.value,
        fileMetadata.value.description,
        fileMetadata.value.name
      );
      ElMessage.success('原始文件上传成功！');
    }

    dataCleaningDialogVisible.value = false;
    // 上传成功后刷新数据源列表
    await fetchDatasets();
    ElMessage.success('数据源列表已更新');
  } catch (error: any) {
    ElMessage.error('文件上传失败: ' + (error?.message || error));
    console.error(error);
  } finally {
    isLoading.value = false;
  }
};

// 完成处理（数据已经上传，关闭对话框）
const completeCleaningAndUpload = async () => {
  if (analysisResult.value?.data_uploaded) {
    // 数据已经上传，直接关闭对话框并刷新列表
    dataCleaningDialogVisible.value = false;
    await fetchDatasets();
    ElMessage.success('数据处理完成！数据源列表已刷新');
  } else {
    // 数据还没有上传（理论上不应该到这里）
    ElMessage.warning('请先选择跳过清洗或执行清洗操作');
  }
};

// 切换清洗动作选择
const toggleCleaningAction = (suggestion: CleaningSuggestion) => {
  const action: CleaningAction = {
    type: suggestion.type,
    column: suggestion.column,
    parameters: suggestion.options?.[0]?.method || '' // 默认选择第一个选项的方法
  };

  const index = selectedCleaningActions.value.findIndex(a =>
    a.type === action.type && a.column === action.column
  );

  if (index >= 0) {
    selectedCleaningActions.value.splice(index, 1);
  } else {
    selectedCleaningActions.value.push(action);
  }
};

// 关闭清洗弹窗
const closeCleaningDialog = () => {
  dataCleaningDialogVisible.value = false;
  currentUploadFile.value = null;
  dataQualityReport.value = null;
  cleaningSuggestions.value = [];
  fieldMappings.value = {};
  selectedCleaningActions.value = [];
  cleaningStep.value = 'upload';
  fileMetadata.value = { name: '', description: '' };
  userRequirements.value = '';
  analysisResult.value = null;
  showAdvancedOptions.value = false;
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

    <!-- 上传区域 -->
    <DataSourceUploadPanel @fileUpload="handleFileUpload" @openDatabaseDialog="openAddDatabase" />

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

    <!-- 数据清洗对话框 -->
    <DataCleaningDialog v-model:visible="dataCleaningDialogVisible" v-model:step="cleaningStep"
      v-model:userRequirements="userRequirements" v-model:selectedModel="selectedModel"
      v-model:fileMetadata="fileMetadata" :file="currentUploadFile" :dataQualityReport="dataQualityReport"
      :cleaningSuggestions="cleaningSuggestions" :fieldMappings="fieldMappings" :isAnalyzing="isSmartAnalyzing"
      :isCleaning="isCleaning" :selectedCleaningActions="selectedCleaningActions" :analysisResult="analysisResult"
      :availableModels="availableModels" @analyze="analyzeDataQualityWithAI" @skipAndUpload="skipCleaningAndUpload"
      @applyCleaningActions="applyCleaningActions" @complete="completeCleaningAndUpload" @close="closeCleaningDialog"
      @toggleCleaningAction="toggleCleaningAction" />

    <!-- 添加数据库对话框 -->
    <AddDatabaseDialog v-model:visible="addDatabaseDialogVisible" @success="onDatabaseAddSuccess" />
  </div>
</template>

<style lang="scss" scoped>
.data-management-container {
  padding: 24px;
  background: #f8fafc;
  min-height: 100vh;
}
</style>
