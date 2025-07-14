<script setup lang="ts">
import { useDataSourceStore } from '@/stores/datasource'
import type { AnyDatabaseConnection, DremioDatabaseType, OracleConnection, PostgreSQLConnection } from '@/types'
import { Connection } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

const visible = defineModel<boolean>('visible', { required: true });

const emit = defineEmits<{
  (e: 'success'): void
}>()

const dataSourceStore = useDataSourceStore()

// 数据库类型选项
const databaseTypes: Array<{ label: string; value: DremioDatabaseType }> = [
  { label: 'MySQL 数据库', value: 'MYSQL' },
  { label: 'PostgreSQL 数据库', value: 'POSTGRES' },
  { label: 'SQL Server 数据库', value: 'MSSQL' },
  { label: 'Oracle 数据库', value: 'ORACLE' }
]

// 表单数据
const formData = reactive({
  database_type: 'MYSQL' as DremioDatabaseType,
  name: '',
  description: '',
  connection: {
    hostname: '',
    port: 3306,
    username: '',
    password: '',
    databaseName: '',  // 用于PostgreSQL
    instance: ''       // 用于Oracle
  }
})

// 表单验证规则
const rules = {
  database_type: [{ required: true, message: '请选择数据库类型', trigger: 'change' }],
  name: [{ required: true, message: '请输入连接名称', trigger: 'blur' }],
  'connection.hostname': [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  'connection.port': [
    { required: true, message: '请输入端口号', trigger: 'blur' },
    { type: 'number', message: '端口号必须为数字', trigger: 'blur' }
  ],
  'connection.username': [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  'connection.password': [{ required: true, message: '请输入密码', trigger: 'blur' }],
  'connection.databaseName': [{ required: true, message: '请输入数据库名称', trigger: 'blur' }],
  'connection.instance': [{ required: true, message: '请输入实例名称', trigger: 'blur' }]
}

const formRef = ref()
const isSubmitting = ref(false)

// 根据数据库类型设置默认端口
watch(() => formData.database_type, (type) => {
  switch (type) {
    case 'MYSQL':
      formData.connection.port = 3306
      break
    case 'POSTGRES':
      formData.connection.port = 5432
      break
    case 'MSSQL':
      formData.connection.port = 1433
      break
    case 'ORACLE':
      formData.connection.port = 1521
      break
  }
})

// 获取当前数据库类型的特定连接字段
const specialFields = computed((): {
  name: 'databaseName' | 'instance'
  label: string
  placeholder: string
}[] => {
  switch (formData.database_type) {
    case 'POSTGRES':
      return [
        { name: 'databaseName', label: '数据库名称', placeholder: '请输入数据库名称' }
      ]
    case 'ORACLE':
      return [
        { name: 'instance', label: '实例名称', placeholder: '请输入Oracle实例名称' }
      ]
    default:
      return []
  }
})

const close = () => {
  visible.value = false
  resetForm()
}

const resetForm = () => {
  formData.database_type = 'MYSQL'
  formData.name = ''
  formData.description = ''
  formData.connection = {
    hostname: '',
    port: 3306,
    username: '',
    password: '',
    databaseName: '',
    instance: ''
  }
  if (formRef.value) {
    formRef.value.resetFields()
  }
}

const submitForm = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()

    isSubmitting.value = true

    // 根据数据库类型准备连接参数
    const connection: AnyDatabaseConnection = {
      hostname: formData.connection.hostname,
      port: formData.connection.port,
      username: formData.connection.username,
      password: formData.connection.password
    }

    // 为特定数据库类型添加额外字段
    if (formData.database_type === 'POSTGRES') {
      (connection as PostgreSQLConnection).databaseName = formData.connection.databaseName
    } else if (formData.database_type === 'ORACLE') {
      (connection as OracleConnection).instance = formData.connection.instance
    }

    // 调用store方法添加数据库连接
    await dataSourceStore.createDatabaseSource({
      database_type: formData.database_type,
      connection: connection,
      name: formData.name,
      description: formData.description || undefined
    })

    ElMessage.success('数据库连接添加成功')
    emit('success')
    close()
  } catch (error) {
    console.error('提交表单失败:', error)
    ElMessage.error('添加数据库连接失败，请检查输入信息是否正确')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="添加数据库连接" width="600px" :before-close="close" destroy-on-close>
    <el-form ref="formRef" :model="formData" :rules="rules" label-width="120px" label-position="top"
      class="database-form">
      <!-- 数据库类型选择 -->
      <el-form-item label="数据库类型" prop="database_type">
        <el-radio-group v-model="formData.database_type">
          <div class="database-type-options">
            <el-radio-button v-for="type in databaseTypes" :key="type.value" :label="type.value"
              class="database-type-option">
              <div class="db-type-content">
                <el-icon class="db-icon">
                  <Connection />
                </el-icon>
                <span class="db-type-name">{{ type.label }}</span>
              </div>
            </el-radio-button>
          </div>
        </el-radio-group>
      </el-form-item>

      <!-- 连接名称和描述 -->
      <div class="form-row">
        <el-form-item label="连接名称" prop="name" class="form-col">
          <el-input v-model="formData.name" placeholder="请输入连接名称" prefix-icon="Edit" clearable />
        </el-form-item>
      </div>

      <el-form-item label="连接描述" prop="description">
        <el-input v-model="formData.description" type="textarea" placeholder="请输入连接描述(可选)" :rows="2" />
      </el-form-item>

      <!-- 通用连接参数 -->
      <div class="form-section-title">连接参数</div>

      <div class="form-row">
        <el-form-item label="主机地址" prop="connection.hostname" class="form-col">
          <el-input v-model="formData.connection.hostname" placeholder="请输入主机地址" clearable />
        </el-form-item>

        <el-form-item label="端口" prop="connection.port" class="form-col">
          <el-input-number v-model="formData.connection.port" :min="1" :max="65535" class="port-input" />
        </el-form-item>
      </div>

      <div class="form-row">
        <el-form-item label="用户名" prop="connection.username" class="form-col">
          <el-input v-model="formData.connection.username" placeholder="请输入用户名" clearable />
        </el-form-item>

        <el-form-item label="密码" prop="connection.password" class="form-col">
          <el-input v-model="formData.connection.password" placeholder="请输入密码" type="password" show-password
            clearable />
        </el-form-item>
      </div>

      <!-- 特定数据库类型的其他参数 -->
      <div v-if="specialFields.length > 0" class="form-row">
        <el-form-item v-for="field in specialFields" :key="field.name" :label="field.label"
          :prop="`connection.${field.name}`" class="form-col">
          <el-input v-model="formData.connection[field.name]" :placeholder="field.placeholder" clearable />
        </el-form-item>
      </div>
    </el-form>

    <!-- 底部按钮 -->
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="close">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="isSubmitting">
          添加连接
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.database-form {
  margin-top: 10px;

  .form-section-title {
    font-weight: 600;
    color: #334155;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e2e8f0;
  }

  .form-row {
    display: flex;
    gap: 16px;
    margin-bottom: 8px;

    .form-col {
      flex: 1;
    }
  }
}

.database-type-options {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;

  .database-type-option {
    flex: 1;
    min-width: 120px;

    :deep(.el-radio-button__inner) {
      width: 100%;
      height: 80px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      transition: all 0.3s ease;
    }

    &:not(:first-child) {
      :deep(.el-radio-button__inner) {
        border-left: 1px solid #e2e8f0;
      }
    }
  }
}

.db-type-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  .db-icon {
    font-size: 24px;
    margin-bottom: 8px;
  }

  .db-type-name {
    font-size: 14px;
    white-space: nowrap;
  }
}

.port-input {
  width: 100%;
}

// 修改单选按钮被选中后的样式
:deep(.el-radio-button__orig-radio:checked + .el-radio-button__inner) {
  background-color: #f0f7ff;
  color: #1d4ed8;
  border-color: #1d4ed8;
  box-shadow: 0 0 0 1px #1d4ed8 inset;
}
</style>
