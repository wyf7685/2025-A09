<script setup lang="ts">
import { UploadFilled, Connection } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

// 定义组件事件，带类型标注
const emit = defineEmits<{
  fileUpload: [options: { file: File; }];
  openDatabaseDialog: [];
}>();

// 处理文件上传
const handleFileUpload = (options: any) => {
  const file = options.file;
  if (!file) return;

  // 检查文件类型
  const allowedTypes = ['csv', 'xlsx', 'xls'];
  const fileExtension = file.name.split('.').pop()?.toLowerCase();

  if (!fileExtension || !allowedTypes.includes(fileExtension)) {
    ElMessage.error('只支持 CSV 和 Excel 文件格式');
    return;
  }

  // 向父组件发送上传事件
  emit('fileUpload', { file });
};

// 打开数据库对话框
const openAddDatabase = () => {
  emit('openDatabaseDialog');
};
</script>

<template>
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
</template>

<style lang="scss" scoped>
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

// 响应式设计
@media (max-width: 768px) {
  .upload-section {
    .el-col {
      margin-bottom: 16px;
    }
  }
}
</style>
