<script setup lang="ts">
import type { AnyMCPConnection, MCPConnection, MCPConnectionTransport } from '@/types/mcp';
import api from '@/utils/api';
import { formatMessage } from '@/utils/tools';
import { ChatDotRound, Connection, Delete, Link, Monitor } from '@element-plus/icons-vue';
import type { FormInstance, FormRules } from 'element-plus';
import { ElButton, ElForm, ElFormItem, ElIcon, ElInput, ElInputNumber, ElMessage, ElOption, ElRadioButton, ElRadioGroup, ElSelect, ElSwitch, ElTag } from 'element-plus';
import { nextTick, onMounted, reactive, ref, watch } from 'vue';

// Props
const props = defineProps<{
  visible: boolean;
  connection: MCPConnection | null;
}>();

// Emits
const emit = defineEmits<{
  save: [data: {
    name: string;
    description?: string;
    connection: AnyMCPConnection;
  }];
  cancel: [];
}>();

// 响应式数据
const formRef = ref<FormInstance>();
const saving = ref(false);
const testing = ref(false);
const showArgInput = ref(false);
const newArg = ref('');
const argInputRef = ref();

// 测试结果
const testResult = ref<{
  success: boolean;
  title?: string;
  description?: string;
  error?: string;
} | null>(null);

// 格式化的markdown描述
const formattedDescription = ref<string>('');

// 表单数据
const formData = reactive({
  name: '',
  description: '',
  transport: 'sse' as MCPConnectionTransport,

  // Stdio 字段
  command: '',
  args: [] as string[],
  cwd: '',
  encoding: 'utf-8',
  envVars: [] as Array<{ key: string; value: string; }>,

  // URL 相关字段 (SSE, HTTP, WebSocket)
  url: '',

  // 超时字段
  timeout: 30,
  sse_read_timeout: 300,

  // HTTP 特有字段
  terminate_on_close: true,

  // 头部字段
  headers: [] as Array<{ key: string; value: string; }>
});

// 表单验证规则
const formRules: FormRules = {
  name: [
    { required: true, message: '请输入连接名称', trigger: 'blur' },
    { min: 1, max: 50, message: '名称长度应在 1 到 50 个字符', trigger: 'blur' }
  ],
  transport: [
    { required: true, message: '请选择传输类型', trigger: 'change' }
  ],
  command: [
    {
      required: true,
      message: '请输入执行命令',
      trigger: 'blur',
      validator: (rule, value, callback) => {
        if (formData.transport === 'stdio' && !value) {
          callback(new Error('请输入执行命令'));
        } else {
          callback();
        }
      }
    }
  ],
  url: [
    {
      required: true,
      message: '请输入URL',
      trigger: 'blur',
      validator: (rule, value, callback) => {
        if (['sse', 'streamable_http', 'websocket'].includes(formData.transport) && !value) {
          callback(new Error('请输入URL'));
        } else if (value) {
          try {
            new URL(value);
            callback();
          } catch {
            callback(new Error('请输入有效的URL'));
          }
        } else {
          callback();
        }
      }
    }
  ]
};

const clearForm = () => {
  formData.name = '';
  formData.description = '';
  formData.transport = 'sse';

  formData.command = '';
  formData.args = [];
  formData.cwd = '';
  formData.encoding = 'utf-8';
  formData.envVars = [];

  formData.url = '';
  formData.timeout = 30;
  formData.sse_read_timeout = 300;
  formData.terminate_on_close = true;
  formData.headers = [];

  testResult.value = null;
};

// 监听传输类型变化
const onTransportChange = () => {
  // 清理相关字段
  if (formData.transport === 'stdio') {
    formData.url = '';
    formData.headers = [];
  } else {
    formData.command = '';
    formData.args = [];
    formData.cwd = '';
    formData.envVars = [];
  }
};

// 参数管理
const showNewArgInput = () => {
  showArgInput.value = true;
  nextTick(() => {
    argInputRef.value?.focus();
  });
};

const addArg = () => {
  if (newArg.value.trim()) {
    formData.args.push(newArg.value.trim());
    newArg.value = '';
  }
  showArgInput.value = false;
};

const removeArg = (index: number) => {
  formData.args.splice(index, 1);
};

// 环境变量管理
const addEnvVar = () => {
  formData.envVars.push({ key: '', value: '' });
};

const removeEnvVar = (index: number) => {
  formData.envVars.splice(index, 1);
};

// 头部管理
const addHeader = () => {
  formData.headers.push({ key: '', value: '' });
};

const removeHeader = (index: number) => {
  formData.headers.splice(index, 1);
};

// 构建连接配置
const buildConnectionConfig = (): AnyMCPConnection => {
  const baseConfig = {
    transport: formData.transport
  };

  switch (formData.transport) {
    case 'stdio':
      return {
        ...baseConfig,
        transport: 'stdio',
        command: formData.command,
        args: formData.args,
        cwd: formData.cwd || null,
        encoding: formData.encoding,
        env: formData.envVars.length > 0
          ? Object.fromEntries(
            formData.envVars
              .filter(env => env.key && env.value)
              .map(env => [env.key, env.value])
          )
          : undefined,
      };

    case 'sse':
      return {
        ...baseConfig,
        transport: 'sse',
        url: formData.url,
        timeout: formData.timeout,
        sse_read_timeout: formData.sse_read_timeout,
        headers: formData.headers.length > 0
          ? Object.fromEntries(
            formData.headers
              .filter(header => header.key && header.value)
              .map(header => [header.key, header.value])
          )
          : null
      };

    case 'streamable_http':
      return {
        ...baseConfig,
        transport: 'streamable_http',
        url: formData.url,
        timeout: formData.timeout,
        sse_read_timeout: formData.sse_read_timeout,
        terminate_on_close: formData.terminate_on_close,
        headers: formData.headers.length > 0
          ? Object.fromEntries(
            formData.headers
              .filter(header => header.key && header.value)
              .map(header => [header.key, header.value])
          )
          : null
      };

    case 'websocket':
      return {
        ...baseConfig,
        transport: 'websocket',
        url: formData.url
      };

    default:
      throw new Error(`Unsupported transport type: ${formData.transport}`);
  }
};

// 处理保存
const handleSave = async () => {
  if (!formRef.value) return;

  try {
    await formRef.value.validate();
    saving.value = true;

    const connectionConfig = buildConnectionConfig();

    emit('save', {
      name: formData.name,
      description: formData.description || undefined,
      connection: connectionConfig
    });
  } catch (error) {
    console.error('表单验证失败:', error);
    ElMessage.error('请检查表单输入');
  } finally {
    saving.value = false;
  }
};

// 测试连接
const handleTestConnection = async () => {
  try {
    testing.value = true;
    testResult.value = null;
    formattedDescription.value = '';

    const connectionConfig = buildConnectionConfig();

    const response = await api.post<{
      success: boolean;
      title: string;
      description: string | null;
    }>('/mcp-connections/test', {
      connection: connectionConfig,
    });

    if (response.data.success) {
      // 格式化描述
      if (response.data.description) {
        formattedDescription.value = await formatMessage(response.data.description);
      }

      testResult.value = {
        success: true,
        title: response.data.title,
        description: response.data.description || undefined,
      };
      ElMessage.success('连接测试成功');
    } else {
      testResult.value = {
        success: false,
        error: response.data.title,
      };
      ElMessage.error('连接测试失败: ' + response.data.title);
    }
  } catch (error) {
    console.error('测试连接失败:', error);
    testResult.value = {
      success: false,
      error: error instanceof Error ? error.message : '未知错误',
    };
    ElMessage.error('测试连接失败');
  } finally {
    testing.value = false;
  }
};

// 处理取消
const handleCancel = () => {
  emit('cancel');
};

// 初始化表单数据
const initFormData = () => {
  if (props.connection) {
    formData.name = props.connection.name;
    formData.description = props.connection.description || '';
    formData.transport = props.connection.connection.transport;

    const conn = props.connection.connection;

    if (conn.transport === 'stdio') {
      formData.command = conn.command;
      formData.args = [...conn.args];
      formData.cwd = conn.cwd || '';
      formData.encoding = conn.encoding;

      if (conn.env) {
        formData.envVars = Object.entries(conn.env).map(([key, value]) => ({ key, value }));
      }
    } else if (['sse', 'streamable_http', 'websocket'].includes(conn.transport)) {
      formData.url = conn.url;

      if (conn.transport === 'sse' || conn.transport === 'streamable_http') {
        formData.timeout = conn.timeout;
        formData.sse_read_timeout = conn.sse_read_timeout;

        if (conn.headers) {
          formData.headers = Object.entries(conn.headers).map(([key, value]) => ({
            key,
            value: String(value)
          }));
        }
      }

      if (conn.transport === 'streamable_http') {
        formData.terminate_on_close = conn.terminate_on_close;
      }
    }
  }
};

// 生命周期
onMounted(() => {
  clearForm();
  initFormData();
});

// 监听连接变化
watch(() => props.connection, () => {
  initFormData();
}, { deep: true });

watch(() => props.visible, (newVal) => {
  if (newVal === false) {
    clearForm();
  }
});
</script>

<template>
  <div class="mcp-connection-form">
    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-width="100px"
      label-position="top">
      <!-- 基本信息 -->
      <div class="form-section">
        <h3 class="section-title">基本信息</h3>

        <el-form-item label="连接名称" prop="name">
          <el-input
            v-model="formData.name"
            placeholder="请输入连接名称"
            maxlength="50"
            show-word-limit />
        </el-form-item>

        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            placeholder="请输入连接描述（可选）"
            :rows="3"
            maxlength="200"
            show-word-limit />
        </el-form-item>
      </div>

      <!-- 传输类型选择 -->
      <div class="form-section">
        <h3 class="section-title">传输类型</h3>

        <el-form-item label="传输方式" prop="transport">
          <el-radio-group v-model="formData.transport" @change="onTransportChange">
            <el-radio-button value="stdio">
              <el-icon>
                <Monitor />
              </el-icon>
              Stdio
            </el-radio-button>
            <el-radio-button value="sse">
              <el-icon>
                <Connection />
              </el-icon>
              SSE
            </el-radio-button>
            <el-radio-button value="streamable_http">
              <el-icon>
                <Link />
              </el-icon>
              HTTP
            </el-radio-button>
            <el-radio-button value="websocket">
              <el-icon>
                <ChatDotRound />
              </el-icon>
              WebSocket
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
      </div>

      <!-- 配置详情 -->
      <div class="form-section">
        <h3 class="section-title">连接配置</h3>

        <!-- Stdio 配置 -->
        <template v-if="formData.transport === 'stdio'">
          <el-form-item label="执行命令" prop="command">
            <el-input
              v-model="formData.command"
              placeholder="例如: python" />
          </el-form-item>

          <el-form-item label="命令参数" prop="args">
            <div class="args-input">
              <el-tag
                v-for="(arg, index) in formData.args"
                :key="index"
                closable
                @close="removeArg(index)"
                style="margin-right: 8px; margin-bottom: 8px;">
                {{ arg }}
              </el-tag>
              <el-input
                v-if="showArgInput"
                ref="argInputRef"
                v-model="newArg"
                size="small"
                style="width: 120px;"
                @keyup.enter="addArg"
                @blur="addArg" />
              <el-button
                v-else
                size="small"
                @click="showNewArgInput">
                + 添加参数
              </el-button>
            </div>
          </el-form-item>

          <el-form-item label="工作目录">
            <el-input
              v-model="formData.cwd"
              placeholder="留空使用默认工作目录" />
          </el-form-item>

          <el-form-item label="文本编码">
            <el-select v-model="formData.encoding" style="width: 200px;">
              <el-option label="UTF-8" value="utf-8" />
              <el-option label="GBK" value="gbk" />
              <el-option label="ASCII" value="ascii" />
            </el-select>
          </el-form-item>

          <!-- 环境变量 -->
          <el-form-item label="环境变量">
            <div class="env-vars">
              <div
                v-for="(envVar, index) in formData.envVars"
                :key="index"
                class="env-var-item">
                <el-input
                  v-model="envVar.key"
                  placeholder="变量名"
                  style="width: 150px; margin-right: 8px;" />
                <el-input
                  v-model="envVar.value"
                  placeholder="变量值"
                  style="width: 200px; margin-right: 8px;" />
                <el-button
                  type="danger"
                  size="small"
                  :icon="Delete"
                  @click="removeEnvVar(index)" />
              </div>
              <el-button
                size="small"
                @click="addEnvVar">
                + 添加环境变量
              </el-button>
            </div>
          </el-form-item>
        </template>

        <!-- SSE 配置 -->
        <template v-else-if="formData.transport === 'sse'">
          <el-form-item label="SSE URL" prop="url">
            <el-input
              v-model="formData.url"
              placeholder="例如: https://api.example.com/events" />
          </el-form-item>

          <el-form-item label="HTTP 超时">
            <el-input-number
              v-model="formData.timeout"
              :min="1"
              :max="300"
              controls-position="right"
              style="width: 200px;" />
            <span class="input-unit">秒</span>
          </el-form-item>

          <el-form-item label="SSE 读取超时">
            <el-input-number
              v-model="formData.sse_read_timeout"
              :min="1"
              :max="3600"
              controls-position="right"
              style="width: 200px;" />
            <span class="input-unit">秒</span>
          </el-form-item>

          <!-- HTTP 头部 -->
          <el-form-item label="HTTP 头部">
            <div class="headers">
              <div
                v-for="(header, index) in formData.headers"
                :key="index"
                class="header-item">
                <el-input
                  v-model="header.key"
                  placeholder="头部名称"
                  style="width: 150px; margin-right: 8px;" />
                <el-input
                  v-model="header.value"
                  placeholder="头部值"
                  style="width: 200px; margin-right: 8px;" />
                <el-button
                  type="danger"
                  size="small"
                  :icon="Delete"
                  @click="removeHeader(index)" />
              </div>
              <el-button
                size="small"
                @click="addHeader">
                + 添加头部
              </el-button>
            </div>
          </el-form-item>
        </template>

        <!-- HTTP 配置 -->
        <template v-else-if="formData.transport === 'streamable_http'">
          <el-form-item label="HTTP URL" prop="url">
            <el-input
              v-model="formData.url"
              placeholder="例如: https://api.example.com/mcp" />
          </el-form-item>

          <el-form-item label="HTTP 超时">
            <el-input-number
              v-model="formData.timeout"
              :min="1"
              :max="300"
              controls-position="right"
              style="width: 200px;" />
            <span class="input-unit">秒</span>
          </el-form-item>

          <el-form-item label="SSE 读取超时">
            <el-input-number
              v-model="formData.sse_read_timeout"
              :min="1"
              :max="3600"
              controls-position="right"
              style="width: 200px;" />
            <span class="input-unit">秒</span>
          </el-form-item>

          <el-form-item label="关闭时终止">
            <el-switch v-model="formData.terminate_on_close" />
          </el-form-item>

          <!-- HTTP 头部 -->
          <el-form-item label="HTTP 头部">
            <div class="headers">
              <div
                v-for="(header, index) in formData.headers"
                :key="index"
                class="header-item">
                <el-input
                  v-model="header.key"
                  placeholder="头部名称"
                  style="width: 150px; margin-right: 8px;" />
                <el-input
                  v-model="header.value"
                  placeholder="头部值"
                  style="width: 200px; margin-right: 8px;" />
                <el-button
                  type="danger"
                  size="small"
                  :icon="Delete"
                  @click="removeHeader(index)" />
              </div>
              <el-button
                size="small"
                @click="addHeader">
                + 添加头部
              </el-button>
            </div>
          </el-form-item>
        </template>

        <!-- WebSocket 配置 -->
        <template v-else-if="formData.transport === 'websocket'">
          <el-form-item label="WebSocket URL" prop="url">
            <el-input
              v-model="formData.url"
              placeholder="例如: ws://localhost:8080/mcp" />
          </el-form-item>
        </template>

        <!-- 测试连接按钮 -->
        <div class="test-connection-section">
          <el-button @click="handleTestConnection" :loading="testing" type="info">
            测试连接
          </el-button>
        </div>

        <!-- 测试结果显示 -->
        <template v-if="testResult">
          <div v-if="testResult.success" class="test-result success">
            <div class="result-header">
              <span class="result-icon">✓</span>
              <span class="result-title">测试成功</span>
            </div>
            <div class="result-content">
              <div class="result-item">
                <span class="result-label">Server Title:</span>
                <span class="result-value">{{ testResult.title }}</span>
              </div>
              <div v-if="testResult.description" class="result-item">
                <span class="result-label">Description:</span>
                <div v-if="formattedDescription" class="markdown-body" v-html="formattedDescription"></div>
                <span v-else class="result-value">{{ testResult.description }}</span>
              </div>
            </div>
          </div>
          <div v-else class="test-result error">
            <div class="result-header">
              <span class="result-icon">✕</span>
              <span class="result-title">测试失败</span>
            </div>
            <div class="result-content">
              <div class="result-item">
                <span class="result-label">错误信息:</span>
                <span class="result-value">{{ testResult.error }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </el-form>

    <!-- 操作按钮 -->
    <div class="form-actions">
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleSave" :loading="saving">
        {{ connection ? '更新' : '创建' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.mcp-connection-form {
  padding: 16px 0;
}

.form-section {
  margin-bottom: 32px;
}

.section-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 8px;
}

.args-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.env-vars,
.headers {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.env-var-item,
.header-item {
  display: flex;
  align-items: center;
}

.input-unit {
  margin-left: 8px;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.test-connection-section {
  margin: 24px 0;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  display: flex;
  justify-content: center;
}

.test-result {
  margin: 16px 0;
  padding: 16px;
  border-radius: 4px;
  border-left: 4px solid;
}

.test-result.success {
  background: #f0f9ff;
  border-left-color: #10b981;
}

.test-result.error {
  background: #fef2f2;
  border-left-color: #ef4444;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
}

.result-icon {
  font-size: 20px;
  font-weight: bold;
}

.test-result.success .result-icon {
  color: #10b981;
}

.test-result.error .result-icon {
  color: #ef4444;
}

.result-title {
  color: var(--el-text-color-primary);
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.result-label {
  color: var(--el-text-color-regular);
  font-weight: 500;
  min-width: 120px;
}

.result-value {
  color: var(--el-text-color-primary);
  word-break: break-all;
  flex: 1;
}

/* Markdown 样式，参考 AssistantText.vue */
:deep(.markdown-body) {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: transparent;
  font-size: 14px;
  color: #374151;
  margin: 0;

  /* 调整代码块样式 */
  pre {
    background-color: #f6f8fa;
    border-radius: 4px;
    padding: 12px;
    border: 1px solid #e1e5e9;
    overflow-x: auto;
  }

  code {
    background-color: #f6f8fa;
    padding: 2px 4px;
    border-radius: 4px;
    font-size: 13px;
  }

  /* 调整表格样式 */
  table {
    display: table;
    width: 100%;
    overflow-x: auto;
    border-collapse: collapse;
    margin: 12px 0;
  }

  table th,
  table td {
    padding: 8px 12px;
    border: 1px solid #e1e5e9;
    text-align: left;
  }

  table th {
    background-color: #f6f8fa;
    font-weight: 600;
  }

  /* 调整图片最大宽度 */
  img {
    max-width: 100%;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  /* 调整标题样式 */
  h1,
  h2,
  h3,
  h4,
  h5,
  h6 {
    color: #1f2937;
    font-weight: 600;
    margin: 8px 0;
  }

  /* 调整链接样式 */
  a {
    color: #10b981;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  /* 调整列表样式 */
  ul,
  ol {
    margin: 8px 0;
    padding-left: 20px;
  }

  li {
    margin: 4px 0;
  }

  /* 调整引用样式 */
  blockquote {
    margin: 12px 0;
    padding: 8px 12px;
    background-color: #f9fafb;
    border-left: 4px solid #10b981;
    border-radius: 4px;
  }

  /* 调整段落样式 */
  p {
    margin: 8px 0;
  }
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 24px;
  border-top: 1px solid var(--el-border-color-lighter);
}

:deep(.el-radio-button__inner) {
  display: flex;
  align-items: center;
  gap: 4px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
