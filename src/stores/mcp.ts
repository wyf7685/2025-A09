import type { Session } from '@/types';
import type { AnyMCPConnection, MCPConnection } from '@/types/mcp';
import { withLoading } from '@/utils/tools';
import { ElMessage } from 'element-plus';
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import api from '../utils/api';

export const useMCPStore = defineStore('mcp', () => {
  // 状态
  const connections = ref<Record<string, MCPConnection>>({});
  const loading = ref(false);
  const error = ref<string | null>(null);

  // 计算属性
  const allConnections = computed(() => Object.values(connections.value));
  const connectionCount = computed(() => allConnections.value.length);

  const loadingWrapper =
    <T extends unknown[], R>(errorMessage: string, fn: (...args: T) => Promise<R>) =>
      (...args: T) =>
        withLoading(
          loading,
          () => {
            error.value = null;
            return fn(...args);
          },
          (err) => {
            error.value = errorMessage;
            console.error(errorMessage, err);
            ElMessage.error(errorMessage);
            throw err;
          },
        );

  // 获取所有MCP连接
  const listConnections = loadingWrapper('获取MCP连接列表失败', async () => {
    const response = await api.get<Record<string, MCPConnection>>('/mcp-connections');
    connections.value = response.data;
    return response.data;
  });

  // 获取指定MCP连接
  const getConnection = loadingWrapper(
    '获取MCP连接失败',
    async (connectionId: string): Promise<MCPConnection> => {
      if (connections.value[connectionId]) {
        return connections.value[connectionId];
      }
      const response = await api.get<MCPConnection>(`/mcp-connections/${connectionId}`);
      connections.value[connectionId] = response.data;
      return response.data;
    },
  );

  // 创建MCP连接
  const createConnection = loadingWrapper(
    '创建MCP连接失败',
    async (name: string, connection: AnyMCPConnection, description?: string) => {
      const response = await api.post<MCPConnection>('/mcp-connections', {
        name,
        description,
        connection,
      });
      connections.value[response.data.id] = response.data;
      ElMessage.success('MCP连接创建成功');
      return response.data;
    },
  );

  // 测试MCP连接
  const testConnection = async (connection: AnyMCPConnection) => {
    const response = await api.post<{
      success: boolean;
      title: string;
      description: string | null;
    }>('/mcp-connections/test', {
      connection,
    });
    return response.data;
  };

  // 更新MCP连接
  const updateConnection = loadingWrapper(
    '更新MCP连接失败',
    async (
      connectionId: string,
      updates: {
        name?: string;
        description?: string;
        connection?: AnyMCPConnection;
      },
    ) => {
      const response = await api.put<MCPConnection>(`/mcp-connections/${connectionId}`, updates);
      connections.value[connectionId] = response.data;
      ElMessage.success('MCP连接更新成功');
      return response.data;
    },
  );

  // 删除MCP连接
  const deleteConnection = loadingWrapper(
    '删除MCP连接失败',
    async (connectionId: string): Promise<void> => {
      await api.delete(`/mcp-connections/${connectionId}`);
      delete connections.value[connectionId];
      ElMessage.success('MCP连接删除成功');
    },
  );

  // 向会话添加MCP连接
  const addConnectionsToSession = loadingWrapper(
    '向会话添加MCP连接失败',
    async (sessionId: string, mcpIds: string[]) => {
      const response = await api.post<Session>(`/sessions/${sessionId}/mcp`, {
        mcp_ids: mcpIds,
      });
      return response.data;
    },
  );

  // 从会话移除MCP连接
  const removeConnectionsFromSession = loadingWrapper(
    '从会话移除MCP连接失败',
    async (sessionId: string, mcpIds: string[]) => {
      const response = await api.delete<Session>(`/sessions/${sessionId}/mcp`, {
        data: { mcp_ids: mcpIds },
      });
      return response.data;
    },
  );

  // 获取会话关联的MCP连接
  const getSessionConnections = loadingWrapper(
    '获取会话MCP连接失败',
    async (sessionId: string): Promise<MCPConnection[]> => {
      const response = await api.get<MCPConnection[]>(`/sessions/${sessionId}/mcp`);
      return response.data;
    },
  );

  // 辅助方法：检查连接是否存在
  const connectionExists = (connectionId: string): boolean => {
    return connectionId in connections.value;
  };

  // 辅助方法：根据名称搜索连接
  const searchConnections = (query: string): MCPConnection[] => {
    if (!query.trim()) return allConnections.value;

    const lowerQuery = query.toLowerCase();
    return allConnections.value.filter(
      (conn) =>
        conn.name.toLowerCase().includes(lowerQuery) ||
        conn.description?.toLowerCase().includes(lowerQuery),
    );
  };

  // 辅助方法：按传输类型分组连接
  const connectionsByTransport = computed(() => {
    const groups: Record<string, MCPConnection[]> = {};

    allConnections.value.forEach((conn) => {
      const transport = conn.connection.transport;
      if (!groups[transport]) {
        groups[transport] = [];
      }
      groups[transport].push(conn);
    });

    return groups;
  });

  return {
    // 状态
    connections: computed(() => connections.value),
    allConnections,
    connectionCount,
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    connectionsByTransport,

    // 方法
    clearError: () => (error.value = null),
    listConnections,
    getConnection,
    createConnection,
    testConnection,
    updateConnection,
    deleteConnection,
    addConnectionsToSession,
    removeConnectionsFromSession,
    getSessionConnections,

    // 辅助方法
    connectionExists,
    searchConnections,
  };
});
