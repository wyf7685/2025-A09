<script setup lang="ts">
import MCPConnectionForm from '@/components/mcp/MCPConnectionForm.vue';
import PageHeader from '@/components/PageHeader.vue';
import { useMCPStore } from '@/stores/mcp';
import type { AnyMCPConnection, MCPConnection } from '@/types/mcp';
import { Delete, Edit, MoreFilled, Plus, Search } from '@element-plus/icons-vue';
import { Icon } from '@iconify/vue';
import {
  ElButton, ElDialog, ElDropdown, ElDropdownItem, ElDropdownMenu,
  ElEmpty, ElIcon, ElInput, ElMessageBox, ElOption, ElSelect, ElTag
} from 'element-plus';
import { computed, onMounted, ref } from 'vue';

// Store
const mcpStore = useMCPStore();

// 响应式数据
const searchQuery = ref('');
const selectedTransport = ref('');
const showCreateDialog = ref(false);
const editingConnection = ref<MCPConnection | null>(null);

// 计算属性
const allConnections = computed(() => mcpStore.allConnections);
const loading = computed(() => mcpStore.loading);

const filteredConnections = computed(() => {
  let connections = searchQuery.value
    ? mcpStore.searchConnections(searchQuery.value)
    : allConnections.value;

  if (selectedTransport.value) {
    connections = connections.filter(
      conn => conn.connection.transport === selectedTransport.value
    );
  }

  return connections;
});

// 获取传输类型标签样式
const getTransportTagType = (transport: string): 'primary' | 'success' | 'warning' | 'info' => {
  const typeMap: Record<string, 'primary' | 'success' | 'warning' | 'info'> = {
    stdio: 'primary',
    sse: 'success',
    streamable_http: 'warning',
    websocket: 'info',
  };
  return typeMap[transport] || 'primary';
};

// 获取传输类型显示标签
const getTransportLabel = (transport: string) => {
  const labelMap: Record<string, string> = {
    stdio: 'Stdio',
    sse: 'SSE',
    streamable_http: 'HTTP',
    websocket: 'WebSocket'
  };
  return labelMap[transport] || transport;
};

// 处理下拉菜单命令
const handleCommand = (command: { action: string; id: string; }) => {
  const { action, id } = command;

  if (action === 'edit') {
    handleEdit(id);
  } else if (action === 'delete') {
    handleDelete(id);
  }
};

// 编辑连接
const handleEdit = (connectionId: string) => {
  const connection = mcpStore.connections[connectionId];
  if (connection) {
    editingConnection.value = connection;
    showCreateDialog.value = true;
  }
};

// 删除连接
const handleDelete = async (connectionId: string) => {
  const connection = mcpStore.connections[connectionId];
  if (!connection) return;

  try {
    await ElMessageBox.confirm(
      `确定要删除连接 "${connection.name}" 吗？此操作不可撤销。`,
      '确认删除',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger'
      }
    );

    await mcpStore.deleteConnection(connectionId);
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除连接失败:', error);
    }
  }
};

// 保存连接
const handleSave = async (connectionData: {
  name: string;
  description?: string;
  connection: AnyMCPConnection;
}) => {
  try {
    if (editingConnection.value) {
      // 更新现有连接
      await mcpStore.updateConnection(editingConnection.value.id, connectionData);
    } else {
      // 创建新连接
      await mcpStore.createConnection(
        connectionData.name,
        connectionData.connection,
        connectionData.description
      );
    }
    handleCancel();
  } catch (error) {
    console.error('保存连接失败:', error);
  }
};

// 取消编辑
const handleCancel = () => {
  showCreateDialog.value = false;
  editingConnection.value = null;
};

// 生命周期
onMounted(async () => {
  try {
    await mcpStore.listConnections();
  } catch (error) {
    console.error('加载连接列表失败:', error);
  }
});
</script>

<template>
  <div class="mcp-connections">
    <!-- 页面头部 -->
    <div class="page-header">
      <PageHeader
        title="MCP 连接管理"
        subtitle="管理和配置 Model Context Protocol 连接" />
      <div class="header-actions">
        <el-button
          type="primary"
          :icon="Plus"
          @click="showCreateDialog = true"
          :loading="loading">
          添加连接
        </el-button>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <div class="toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索连接名称或描述..."
        :prefix-icon="Search"
        clearable
        style="width: 300px" />
      <el-select
        v-model="selectedTransport"
        placeholder="按传输类型筛选"
        clearable
        style="width: 200px; margin-left: 12px">
        <el-option label="全部" value="" />
        <el-option label="Stdio" value="stdio" />
        <el-option label="SSE" value="sse" />
        <el-option label="HTTP" value="streamable_http" />
        <el-option label="WebSocket" value="websocket" />
      </el-select>
    </div>

    <!-- 连接列表 -->
    <div class="connections-grid" v-loading="loading">
      <div
        v-for="connection in filteredConnections"
        :key="connection.id"
        class="connection-card">
        <div class="card-header">
          <div class="connection-info">
            <h3 class="connection-name">{{ connection.name }}</h3>
            <pre class="connection-description" v-if="connection.description">{{ connection.description }}</pre>
          </div>
          <div class="connection-actions">
            <el-dropdown @command="handleCommand" trigger="click">
              <el-button :icon="MoreFilled" circle />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="{ action: 'edit', id: connection.id }">
                    <el-icon>
                      <Edit />
                    </el-icon>
                    编辑
                  </el-dropdown-item>
                  <el-dropdown-item
                    :command="{ action: 'delete', id: connection.id }"
                    divided>
                    <el-icon style="color: var(--el-color-danger)">
                      <Delete />
                    </el-icon>
                    <span style="color: var(--el-color-danger)">删除</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <div class="card-body">
          <div class="transport-info">
            <el-tag :type="getTransportTagType(connection.connection.transport)">
              {{ getTransportLabel(connection.connection.transport) }}
            </el-tag>
          </div>

          <div class="connection-details">
            <template v-if="connection.connection.transport === 'stdio'">
              <div class="detail-item">
                <span class="label">命令:</span>
                <code class="value">{{ connection.connection.command }}</code>
              </div>
              <div class="detail-item" v-if="connection.connection.args.length">
                <span class="label">参数:</span>
                <code class="value">{{ connection.connection.args.join(' ') }}</code>
              </div>
            </template>

            <template v-else-if="['sse', 'streamable_http', 'websocket'].includes(connection.connection.transport)">
              <div class="detail-item">
                <span class="label">URL:</span>
                <code class="value">{{ connection.connection.url }}</code>
              </div>
            </template>
          </div>

          <div class="connection-id">
            <span class="label">ID:</span>
            <code class="id-value">{{ connection.id }}</code>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredConnections.length === 0 && !loading" class="empty-state">
        <div v-if="!searchQuery && !selectedTransport" class="empty-content">
          <div class="empty-icon">
            <Icon icon="material-symbols:hub-outline" />
          </div>
          <h3 class="empty-title">暂无 MCP 连接</h3>
          <p class="empty-description">还没有配置任何模型上下文协议连接</p>
          <p class="empty-tip">添加 MCP 连接来扩展您的分析能力</p>
          <div class="empty-action-wrapper">
            <el-button type="primary" @click="showCreateDialog = true" class="empty-action">
              <Icon icon="material-symbols:add" class="button-icon" />
              添加第一个连接
            </el-button>
          </div>
        </div>
        <el-empty v-else :description="'没有找到匹配的连接'" :image-size="120" />
      </div>
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showCreateDialog" :title="editingConnection ? '编辑连接' : '添加 MCP 连接'" width="600px"
      :close-on-click-modal="false">
      <MCPConnectionForm :visible="showCreateDialog" :connection="editingConnection" @save="handleSave"
        @cancel="handleCancel" />
    </el-dialog>
  </div>
</template>

<style scoped>
.mcp-connections {
  min-height: 100vh;
  background: #f8fafc;
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding: 0 8px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.toolbar {
  background: white;
  padding: 16px 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.connections-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
  min-height: 200px;
}

.connection-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 20px;
  background: var(--el-bg-color);
  transition: all 0.3s ease;
}

.connection-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.connection-info {
  flex: 1;
}

.connection-name {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.connection-description {
  margin: 0;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1.4;
}

.connection-actions {
  margin-left: 12px;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.transport-info {
  margin-bottom: 16px;
}

.connection-details {
  margin-bottom: 16px;
}

.detail-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.detail-item:last-child {
  margin-bottom: 0;
}

.label {
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin-right: 8px;
  min-width: 40px;
}

.value {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  word-break: break-all;
  flex: 1;
}

.connection-id {
  display: flex;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.id-value {
  background: var(--el-fill-color-lighter);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: var(--el-text-color-secondary);
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 16px;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(226, 232, 240, 0.6);
}

.empty-content {
  text-align: center;
  max-width: 400px;
}

.empty-icon {
  font-size: 80px;
  color: #06b6d4;
  margin-bottom: 24px;
  filter: drop-shadow(0 4px 12px rgba(6, 182, 212, 0.2));
}

.empty-title {
  margin: 0 0 16px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1e293b;
}

.empty-description {
  margin: 0 0 8px 0;
  color: #64748b;
  font-size: 16px;
  line-height: 1.5;
}

.empty-tip {
  color: #64748b;
  margin: 0 0 32px 0;
  font-size: 16px;
  line-height: 1.5;
}

.empty-action-wrapper {
  display: flex;
  justify-content: center;
  width: 100%;
}

.empty-action {
  border-radius: 12px;
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s ease;
}

.empty-action:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(99, 102, 241, 0.3);
}

.button-icon {
  font-size: 18px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .mcp-connections {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .connections-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .connection-card {
    padding: 16px;
  }
}
</style>
