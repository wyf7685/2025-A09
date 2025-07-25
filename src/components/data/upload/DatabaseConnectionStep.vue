<script setup lang="ts">
import type { AnyDatabaseConnection, DremioDatabaseType } from '@/types';
import { Connection, ArrowLeft } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, reactive, ref, watch } from 'vue';

// 双向绑定数据
const connectionName = defineModel<string>('connectionName', { required: true });
const connectionDescription = defineModel<string>('connectionDescription', { default: '' });

// 定义事件
const emit = defineEmits<{
  connect: [params: {
    database_type: DremioDatabaseType;
    connection: AnyDatabaseConnection;
    name: string;
    description: string;
  }];
  goBack: [];
}>();

// 数据库类型选项
const databaseTypes: Array<{ label: string; value: DremioDatabaseType; }> = [
  { label: 'MySQL 数据库', value: 'MYSQL' },
  { label: 'PostgreSQL 数据库', value: 'POSTGRES' },
  { label: 'SQL Server 数据库', value: 'MSSQL' },
  { label: 'Oracle 数据库', value: 'ORACLE' }
];

// 表单数据
const formData = reactive({
  database_type: 'MYSQL' as DremioDatabaseType,
  connection: {
    hostname: '',
    port: 3306,
    username: '',
    password: '',
    databaseName: '',  // 用于PostgreSQL
    instance: '',      // 用于Oracle
  }
});

// 表单验证规则
const rules = {
  database_type: [{ required: true, message: '请选择数据库类型', trigger: 'change' }],
  'connection.hostname': [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  'connection.port': [
    { type: 'number', message: '端口号必须为数字', trigger: 'blur' }
  ],
  'connection.username': [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  'connection.password': [{ required: true, message: '请输入密码', trigger: 'blur' }],
  'connection.databaseName': [{ required: true, message: '请输入数据库名称', trigger: 'blur' }],
  'connection.instance': [{ required: true, message: '请输入实例名称', trigger: 'blur' }]
};

const formRef = ref();
const isSubmitting = ref(false);

// 根据数据库类型设置默认端口
watch(() => formData.database_type, (type) => {
  switch (type) {
    case 'MYSQL':
      formData.connection.port = 3306;
      break;
    case 'POSTGRES':
      formData.connection.port = 5432;
      break;
    case 'MSSQL':
      formData.connection.port = 1433;
      break;
    case 'ORACLE':
      formData.connection.port = 1521;
      break;
  }
});

// 获取当前数据库类型的特定连接字段
const specialFields = computed(() => {
  switch (formData.database_type) {
    case 'POSTGRES':
      return [
        {
          name: 'databaseName' as const,
          label: '数据库名称',
          placeholder: '请输入数据库名称'
        }
      ];
    case 'ORACLE':
      return [
        {
          name: 'instance' as const,
          label: '实例名称',
          placeholder: '请输入Oracle实例名称'
        }
      ];
    default:
      return [];
  }
});

const goBack = () => {
  emit('goBack');
};

const submitForm = async () => {
  if (!formRef.value) return;

  await formRef.value.validate();

  if (!connectionName.value) {
    ElMessage.warning('请输入连接名称');
    return;
  }

  isSubmitting.value = true;

  try {
    // 构建连接参数
    const connectionParams = {
      database_type: formData.database_type,
      name: connectionName.value,
      description: connectionDescription.value,
      connection: { ...formData.connection } as AnyDatabaseConnection
    };

    emit('connect', connectionParams);
  } finally {
    isSubmitting.value = false;
  }
};
</script>

<template>
  <div class="database-connection-step">
    <div class="back-button">
      <el-button @click="goBack" text>
        <el-icon>
          <ArrowLeft />
        </el-icon>
        返回
      </el-button>
    </div>

    <h2 class="title">添加数据库连接</h2>

    <el-form ref="formRef" :model="formData" :rules="rules" label-position="top" class="database-form">
      <h3 class="form-section-title">选择数据库类型</h3>
      <div class="database-type-options">
        <el-radio-group v-model="formData.database_type">
          <el-radio-button v-for="dbType in databaseTypes" :key="dbType.value" :label="dbType.value"
            class="database-type-option">
            <div class="db-type-content">
              <el-icon class="db-icon" size="24">
                <Connection />
              </el-icon>
              <span class="db-type-name">{{ dbType.label }}</span>
            </div>
          </el-radio-button>
        </el-radio-group>
      </div>

      <h3 class="form-section-title">连接基本信息</h3>
      <el-form-item label="连接名称" prop="name">
        <el-input v-model="connectionName" placeholder="请输入连接名称" />
      </el-form-item>

      <el-form-item label="连接描述" prop="description">
        <el-input v-model="connectionDescription" type="textarea" :rows="2" placeholder="请输入连接描述（可选）" />
      </el-form-item>

      <h3 class="form-section-title">连接参数</h3>
      <el-form-item label="主机地址" prop="connection.hostname">
        <el-input v-model="formData.connection.hostname" placeholder="例如: localhost 或 192.168.1.100" />
      </el-form-item>

      <div class="form-row">
        <el-form-item label="端口号" prop="connection.port" class="port-input">
          <el-input-number v-model="formData.connection.port" :min="1" :max="65535" />
        </el-form-item>
      </div>

      <el-form-item label="用户名" prop="connection.username">
        <el-input v-model="formData.connection.username" placeholder="请输入数据库用户名" />
      </el-form-item>

      <el-form-item label="密码" prop="connection.password">
        <el-input v-model="formData.connection.password" type="password" placeholder="请输入数据库密码" show-password />
      </el-form-item>

      <!-- 特定数据库的额外字段 -->
      <template v-for="field in specialFields" :key="field.name">
        <el-form-item :label="field.label" :prop="`connection.${field.name}`">
          <el-input v-model="formData.connection[field.name]" :placeholder="field.placeholder" />
        </el-form-item>
      </template>

      <div class="form-actions">
        <el-button @click="goBack">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="isSubmitting">连接数据库</el-button>
      </div>
    </el-form>
  </div>
</template>

<style lang="scss" scoped>
.database-connection-step {
  max-width: 700px;
  margin: 0 auto;
  padding: 0 20px 40px;

  .back-button {
    margin-bottom: 20px;
  }

  .title {
    font-size: 24px;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 24px;
  }

  .database-form {
    margin-top: 10px;

    .form-section-title {
      font-size: 18px;
      font-weight: 500;
      color: #2c3e50;
      margin: 24px 0 16px;
    }

    .form-row {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
    }
  }

  .database-type-options {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 24px;

    .database-type-option {
      flex: 1;
      min-width: 120px;
    }
  }

  .db-type-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 8px 0;

    .db-icon {
      margin-bottom: 8px;
    }

    .db-type-name {
      font-size: 14px;
    }
  }

  .port-input {
    width: 25%;

    :deep(.el-input-number) {
      width: 100%;
    }
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 32px;
    gap: 12px;
  }
}

// 修改单选按钮被选中后的样式
:deep(.el-radio-button__orig-radio:checked + .el-radio-button__inner) {
  background-color: #f0f7ff;
  color: #1d4ed8;
  border-color: #1d4ed8;
  box-shadow: 0 0 0 1px #1d4ed8 inset;
}
</style>
