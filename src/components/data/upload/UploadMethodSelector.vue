<script setup lang="ts">
import { Connection, Upload } from '@element-plus/icons-vue';
import { ElButton, ElIcon } from 'element-plus';

// 定义上传方法类型
type UploadMethod = 'file' | 'database';

// 使用defineModel实现数据双向绑定
const selectedMethod = defineModel<UploadMethod>('selectedMethod', { required: true });

// 定义事件
const emit = defineEmits<{
  proceed: [];
}>();

// 选择上传方法并进行下一步
const selectMethod = (method: UploadMethod) => {
  selectedMethod.value = method;
};

// 进入下一步
const goToNextStep = () => {
  emit('proceed');
};
</script>

<template>
  <div class="upload-method-selector">
    <h2 class="title">选择数据导入方式</h2>
    <p class="subtitle">从以下选项中选择一种方式导入您的数据</p>

    <div class="method-cards">
      <div class="method-card" :class="{ selected: selectedMethod === 'file' }" @click="selectMethod('file')">
        <div class="card-icon">
          <el-icon size="48">
            <Upload />
          </el-icon>
        </div>
        <div class="card-content">
          <h3>上传文件</h3>
          <p>支持上传 CSV、Excel 文件</p>
        </div>
      </div>

      <div class="method-card" :class="{ selected: selectedMethod === 'database' }" @click="selectMethod('database')">
        <div class="card-icon">
          <el-icon size="48">
            <Connection />
          </el-icon>
        </div>
        <div class="card-content">
          <h3>连接数据库</h3>
          <p>支持连接 MySQL、PostgreSQL、SQL Server 和 Oracle 数据库</p>
        </div>
      </div>
    </div>

    <div class="actions">
      <el-button type="primary" size="large" @click="goToNextStep" :disabled="!selectedMethod">
        下一步
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.upload-method-selector {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 20px;

  .title {
    font-size: 24px;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 8px;
    text-align: center;
  }

  .subtitle {
    font-size: 16px;
    color: #6b7280;
    margin-bottom: 32px;
    text-align: center;
  }

  .method-cards {
    display: flex;
    gap: 24px;
    margin-bottom: 40px;
    justify-content: center;
    flex-wrap: wrap;

    .method-card {
      flex: 1;
      min-width: 300px;
      max-width: 450px;
      background: white;
      border-radius: 16px;
      padding: 32px;
      display: flex;
      flex-direction: column;
      align-items: center;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
      cursor: pointer;
      transition: all 0.3s ease;
      border: 2px solid transparent;

      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
      }

      &.selected {
        border-color: #1d4ed8;
        background-color: #f0f7ff;
      }

      .card-icon {
        margin-bottom: 24px;
        color: #1d4ed8;
      }

      .card-content {
        text-align: center;

        h3 {
          font-size: 20px;
          font-weight: 600;
          color: #2c3e50;
          margin-bottom: 12px;
        }

        p {
          font-size: 15px;
          color: #6b7280;
          line-height: 1.6;
        }
      }
    }
  }

  .actions {
    display: flex;
    justify-content: center;
  }
}

@media (max-width: 768px) {
  .upload-method-selector {
    .method-cards {
      flex-direction: column;
      align-items: center;
    }
  }
}
</style>
