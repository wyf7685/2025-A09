<template>
  <div class="mcp-manager">
    <!-- MCP管理头部 -->
    <div class="mcp-header">
      <div class="header-left">
        <el-icon>
          <Link />
        </el-icon>
        <span class="title">MCP 连接</span>
        <el-badge :value="sessionMCPConnections.length" :max="99" v-if="sessionMCPConnections.length > 0" />
      </div>
      <div class="header-right">
        <el-button
          size="small"
          type="primary"
          :icon="Plus"
          @click="showMCPSelector = true"
          :disabled="!currentSessionId">
          添加
        </el-button>
      </div>
    </div>

    <!-- 当前会话的MCP连接列表 -->
    <div class="mcp-list" v-if="sessionMCPConnections.length > 0">
      <div
        v-for="connection in sessionMCPConnections"
        :key="connection.id"
        class="mcp-item">
        <div class="mcp-info">
          <div class="mcp-name">{{ connection.name }}</div>
          <div class="mcp-type">
            <el-tag :type="getTransportTagType(connection.connection.transport)" size="small">
              {{ getTransportLabel(connection.connection.transport) }}
            </el-tag>
          </div>
        </div>
        <div class="mcp-actions">
          <el-button
            size="small"
            type="danger"
            :icon="Delete"
            @click="removeMCPFromSession(connection.id)"
            :loading="removing === connection.id" />
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <el-icon>
        <Connection />
      </el-icon>
      <span>暂无 MCP 连接</span>
      <el-button
        v-if="currentSessionId"
        size="small"
        type="primary"
        text
        @click="showMCPSelector = true">
        立即添加
      </el-button>
    </div>

    <!-- MCP选择对话框 -->
    <el-dialog
      v-model="showMCPSelector"
      title="添加 MCP 连接"
      width="500px"
      :close-on-click-modal="false">
      <div class="mcp-selector">
        <div class="selector-header">
          <el-input
            v-model="searchQuery"
            placeholder="搜索 MCP 连接..."
            :prefix-icon="Search"
            clearable />
        </div>

        <div class="available-connections" v-loading="mcpStore.loading">
          <div
            v-for="connection in filteredAvailableConnections"
            :key="connection.id"
            class="connection-option"
            :class="{ selected: selectedConnections.includes(connection.id) }"
            @click="toggleConnection(connection.id)">
            <div class="connection-info">
              <div class="connection-name">{{ connection.name }}</div>
              <div class="connection-description" v-if="connection.description">
                {{ connection.description }}
              </div>
              <el-tag :type="getTransportTagType(connection.connection.transport)" size="small">
                {{ getTransportLabel(connection.connection.transport) }}
              </el-tag>
            </div>
            <div class="connection-checkbox">
              <el-checkbox :model-value="selectedConnections.includes(connection.id)" />
            </div>
          </div>

          <div v-if="filteredAvailableConnections.length === 0" class="no-connections">
            <el-icon>
              <Connection />
            </el-icon>
            <span>{{ searchQuery ? '没有找到匹配的连接' : '暂无可用的 MCP 连接' }}</span>
            <el-button
              type="primary"
              text
              @click="goToMCPManagement">
              前往管理 MCP 连接
            </el-button>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showMCPSelector = false">取消</el-button>
          <el-button
            type="primary"
            @click="addSelectedConnections"
            :disabled="selectedConnections.length === 0"
            :loading="adding">
            添加 ({{ selectedConnections.length }})
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { useMCPStore } from '@/stores/mcp';
import { useSessionStore } from '@/stores/session';
import type { MCPConnection } from '@/types/mcp';
import {
  Connection,
  Delete,
  Link,
  Plus,
  Search
} from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

// Props
interface Props {
  currentSessionId?: string;
}

const props = defineProps<Props>();

// Stores
const mcpStore = useMCPStore();
const sessionStore = useSessionStore();
const router = useRouter();

// 响应式数据
const showMCPSelector = ref(false);
const searchQuery = ref('');
const selectedConnections = ref<string[]>([]);
const sessionMCPConnections = ref<MCPConnection[]>([]);
const adding = ref(false);
const removing = ref<string | null>(null);

// 计算属性
const filteredAvailableConnections = computed(() => {
  let connections = mcpStore.allConnections;

  // 过滤已添加到当前会话的连接
  const sessionMCPIds = sessionMCPConnections.value.map(c => c.id);
  connections = connections.filter(c => !sessionMCPIds.includes(c.id));

  // 搜索过滤
  if (searchQuery.value) {
    connections = mcpStore.searchConnections(searchQuery.value)
      .filter(c => !sessionMCPIds.includes(c.id));
  }

  return connections;
});

// 获取传输类型标签样式
const getTransportTagType = (transport: string) => {
  const typeMap: Record<string, string> = {
    stdio: 'primary',
    sse: 'success',
    streamable_http: 'warning',
    websocket: 'info'
  };
  return typeMap[transport] || 'default';
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

// 切换连接选择
const toggleConnection = (connectionId: string) => {
  const index = selectedConnections.value.indexOf(connectionId);
  if (index > -1) {
    selectedConnections.value.splice(index, 1);
  } else {
    selectedConnections.value.push(connectionId);
  }
};

// 添加选中的连接到会话
const addSelectedConnections = async () => {
  if (!props.currentSessionId || selectedConnections.value.length === 0) return;

  try {
    adding.value = true;

    await mcpStore.addConnectionsToSession(
      props.currentSessionId,
      selectedConnections.value
    );

    // 刷新会话的MCP连接
    await loadSessionMCPConnections();

    // 重置选择
    selectedConnections.value = [];
    showMCPSelector.value = false;

    ElMessage.success(`成功添加 ${selectedConnections.value.length} 个 MCP 连接`);
  } catch (error) {
    console.error('添加 MCP 连接失败:', error);
  } finally {
    adding.value = false;
  }
};

// 从会话移除MCP连接
const removeMCPFromSession = async (connectionId: string) => {
  if (!props.currentSessionId) return;

  try {
    removing.value = connectionId;

    await mcpStore.removeConnectionsFromSession(
      props.currentSessionId,
      [connectionId]
    );

    // 刷新会话的MCP连接
    await loadSessionMCPConnections();

    ElMessage.success('MCP 连接已移除');
  } catch (error) {
    console.error('移除 MCP 连接失败:', error);
  } finally {
    removing.value = null;
  }
};

// 加载会话的MCP连接
const loadSessionMCPConnections = async () => {
  if (!props.currentSessionId) {
    sessionMCPConnections.value = [];
    return;
  }

  try {
    const connections = await mcpStore.getSessionConnections(props.currentSessionId);
    sessionMCPConnections.value = connections;
  } catch (error) {
    console.error('加载会话 MCP 连接失败:', error);
    sessionMCPConnections.value = [];
  }
};

// 前往MCP管理页面
const goToMCPManagement = () => {
  showMCPSelector.value = false;
  router.push('/mcp-connections');
};

// 监听当前会话变化
watch(
  () => props.currentSessionId,
  (newSessionId) => {
    if (newSessionId) {
      loadSessionMCPConnections();
    } else {
      sessionMCPConnections.value = [];
    }
  },
  { immediate: true }
);

// 生命周期
onMounted(async () => {
  // 加载所有MCP连接
  try {
    await mcpStore.listConnections();
  } catch (error) {
    console.error('加载 MCP 连接失败:', error);
  }

  // 加载当前会话的MCP连接
  if (props.currentSessionId) {
    await loadSessionMCPConnections();
  }
});

// 暴露方法给父组件
defineExpose({
  refreshConnections: loadSessionMCPConnections
});
</script>

<style scoped>
.mcp-manager {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.mcp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.mcp-list {
  padding: 8px;
}

.mcp-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.mcp-item:hover {
  background: var(--el-fill-color-light);
}

.mcp-info {
  flex: 1;
}

.mcp-name {
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.mcp-type {
  margin-top: 4px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  color: var(--el-text-color-secondary);
  gap: 8px;
}

.mcp-selector {
  padding: 0;
}

.selector-header {
  margin-bottom: 16px;
}

.available-connections {
  max-height: 400px;
  overflow-y: auto;
}

.connection-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.connection-option:hover {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.connection-option.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-8);
}

.connection-info {
  flex: 1;
}

.connection-name {
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.connection-description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.no-connections {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 16px;
  color: var(--el-text-color-secondary);
  gap: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
