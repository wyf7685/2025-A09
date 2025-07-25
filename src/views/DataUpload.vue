<script setup lang="ts">
import DatabaseConnectionStep from '@/components/data/upload/DatabaseConnectionStep.vue';
import FileUploadStep from '@/components/data/upload/FileUploadStep.vue';
import UploadMethodSelector from '@/components/data/upload/UploadMethodSelector.vue';
import { useDataSourceStore } from '@/stores/datasource';
import { useModelStore } from '@/stores/model';
import type { AnyDatabaseConnection, DremioDatabaseType } from '@/types';
import { dataSourceAPI } from '@/utils/api';
import { ElMessage } from 'element-plus';
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowRight } from '@element-plus/icons-vue';

const router = useRouter();
const dataSourceStore = useDataSourceStore();
const modelStore = useModelStore();

// 控制当前视图状态
const currentStep = ref<'method' | 'fileUpload' | 'database'>('method');
const selectedMethod = ref<'file' | 'database'>('file');

// 文件上传相关状态
const selectedFile = ref<File | null>(null);
const fileName = ref('');
const fileDescription = ref('');
const userRequirements = ref('');
const selectedModel = ref('');
const isUploading = ref(false);

// 数据库连接相关状态
const connectionName = ref('');
const connectionDescription = ref('');
const isConnecting = ref(false);

// 可用模型列表
const availableModels = ref<Array<{ value: string, label: string; }>>([]);

// 获取可用模型列表
onMounted(async () => {
  try {
    const models = await modelStore.fetchAvailableModels();
    availableModels.value = models.map(model => ({
      value: model.id,
      label: model.name
    }));
  } catch (error) {
    console.error('Failed to fetch models:', error);
    ElMessage.error('获取模型列表失败');
  }
});

// 处理上传方法选择
const handleMethodSelection = () => {
  currentStep.value = selectedMethod.value === 'file' ? 'fileUpload' : 'database';
};

// 处理返回上一步
const goBack = () => {
  currentStep.value = 'method';
};

// 处理文件选择
const handleFileSelected = (file: File) => {
  selectedFile.value = file;

  // 如果文件名为空，则使用文件名
  if (!fileName.value) {
    fileName.value = file.name.split('.')[0];
  }
};

// 处理文件上传
const handleFileUpload = async (cleanedFileId?: string) => {
  if (!selectedFile.value && !cleanedFileId) {
    ElMessage.warning('请选择要上传的文件');
    return;
  }

  if (!fileName.value) {
    ElMessage.warning('请输入文件名称');
    return;
  }

  isUploading.value = true;

  try {
    if (cleanedFileId) {
      // 如果有已清洗的文件ID，使用该ID上传
      await dataSourceAPI.uploadCleanedFile(
        cleanedFileId,
        fileName.value,
        fileDescription.value,
      );
    } else {
      // 否则直接上传原文件
      await dataSourceStore.uploadFileSource(
        selectedFile.value!,
        fileDescription.value,
        fileName.value
      );
    }

    ElMessage.success('文件上传成功');

    // 上传成功后跳转回数据管理页面
    router.push('/data-management');
  } catch (error) {
    console.error('File upload failed:', error);
    ElMessage.error('文件上传失败');
  } finally {
    isUploading.value = false;
  }
};

// 处理数据库连接
const handleDatabaseConnect = async (params: {
  database_type: DremioDatabaseType;
  connection: AnyDatabaseConnection;
  name: string;
  description: string;
}) => {
  isConnecting.value = true;

  try {
    await dataSourceStore.createDatabaseSource({
      database_type: params.database_type,
      connection: params.connection,
      name: params.name,
      description: params.description
    });

    ElMessage.success('数据库连接成功');

    // 连接成功后跳转回数据管理页面
    router.push('/data-management');
  } catch (error) {
    console.error('Database connection failed:', error);
    ElMessage.error('数据库连接失败');
  } finally {
    isConnecting.value = false;
  }
};
</script>

<template>
  <div class="data-upload-view" v-loading="isUploading || isConnecting"
    :element-loading-text="isUploading ? '文件上传中...' : '连接数据库中...'"
    element-loading-background="rgba(255, 255, 255, 0.7)">
    <div class="breadcrumb-container">
      <el-breadcrumb :separator-icon="ArrowRight">
        <el-breadcrumb-item :to="{ path: '/data-management' }">数据管理</el-breadcrumb-item>
        <el-breadcrumb-item @click="currentStep = 'method'">数据上传</el-breadcrumb-item>
        <el-breadcrumb-item v-if="currentStep !== 'method'">
          {{ selectedMethod === 'file' ? '文件上传' : '数据库连接' }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="content-container">
      <!-- 步骤1：选择上传方式 -->
      <UploadMethodSelector v-if="currentStep === 'method'" v-model:selectedMethod="selectedMethod"
        @proceed="handleMethodSelection" />

      <!-- 步骤2A：文件上传 -->
      <FileUploadStep v-if="currentStep === 'fileUpload'" v-model:fileName="fileName"
        v-model:fileDescription="fileDescription" v-model:userRequirements="userRequirements"
        v-model:selectedModel="selectedModel" v-model:selected-file="selectedFile" :availableModels="availableModels"
        @fileSelected="handleFileSelected" @goBack="goBack" @proceed="handleFileUpload" />

      <!-- 步骤2B：数据库连接 -->
      <DatabaseConnectionStep v-if="currentStep === 'database'" v-model:connectionName="connectionName"
        v-model:connectionDescription="connectionDescription" @goBack="goBack" @connect="handleDatabaseConnect" />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.data-upload-view {
  padding: 20px;
  background-color: #f9fafb;
  min-height: calc(100vh - 60px); // 减去顶部导航的高度

  .breadcrumb-container {
    margin-bottom: 24px;
    background-color: white;
    padding: 16px 20px;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }

  .content-container {
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    padding: 24px;
  }
}
</style>
