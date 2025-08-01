<script setup lang="ts">
import type { DataSourceMetadata } from '@/types';
import type { MCPConnection } from '@/types/mcp';
import { turncateString } from '@/utils/tools';
import { DataAnalysis, Document, DocumentCopy, Link, PieChart, Search, WarningFilled } from '@element-plus/icons-vue';
import { ElButton, ElDivider, ElIcon, ElInput, ElLink, ElTag, ElTooltip } from 'element-plus';

const props = defineProps<{
  isProcessingChat: boolean;
  currentDatasets?: DataSourceMetadata[] | null;
  mcpConnections?: MCPConnection[] | null;
}>();

const input = defineModel<string>('input', { required: true });

const emit = defineEmits<{
  'send': [];        // 发送消息
  'go-to-data': [];  // 前往数据管理
}>();

// 快速问题模板
const quickQuestions = [
  { text: '基本统计', icon: DataAnalysis, prompt: '分析数据的基本统计信息' },
  { text: '相关性分析', icon: PieChart, prompt: '绘制各列的相关性热力图' },
  { text: '异常检测', icon: Search, prompt: '检测并可视化异常值' },
  { text: '质量报告', icon: Document, prompt: '生成数据质量报告' }
];

// 发送消息
const sendMessage = () => {
  if (!input.value.trim() || props.isProcessingChat) return;
  emit('send');
};

// 前往数据管理
const goToAddData = () => {
  emit('go-to-data');
};

// 监听回车键发送消息（除非按下 shift 键）
const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
};

const formatDatasetsTooltip = (names: string[]) => {
  if (names.length === 0) return '无数据集';
  if (names.length === 1) return names[0];
  return `共 ${names.length} 个数据集: ${names.slice(0, 2).map(s => turncateString(s, 20)).join(', ')} ${names.length > 3 ? '等' : ''}`;
};

const formatMCPTooltip = (connections: MCPConnection[]) => {
  if (connections.length === 0) return '无 MCP 连接';
  if (connections.length === 1) return connections[0].name;
  return `共 ${connections.length} 个 MCP 连接: ${connections.slice(0, 2).map(c => turncateString(c.name, 20)).join(', ')} ${connections.length > 2 ? '等' : ''}`;
};

// 获取传输类型标签样式
const getTransportTagType = (transport: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const typeMap: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    stdio: 'primary',
    sse: 'success',
    streamable_http: 'warning',
    websocket: 'info'
  };
  return typeMap[transport] || 'primary';
};
</script>

<template>
  <div class="chat-input-area">
    <div class="chat-input-wrapper">
      <el-input v-model="input" placeholder="输入你的问题..." @keydown="handleKeydown($event as KeyboardEvent)" resize="none"
        type="textarea" :autosize="{ minRows: 1, maxRows: 5 }" :disabled="isProcessingChat" />
      <el-button @click="sendMessage" :disabled="isProcessingChat || !input.trim()" type="primary" class="send-button">
        发送
      </el-button>
    </div>
    <div class="quick-actions">
      <el-tooltip placement="top" :content="formatDatasetsTooltip(currentDatasets?.map(ds => ds.name || ds.id) || [])">
        <div class="dataset-indicator">
          <el-icon>
            <DocumentCopy v-if="currentDatasets?.length" />
            <WarningFilled v-else />
          </el-icon>
          <template v-if="currentDatasets?.length">
            当前数据集:
            <strong v-if="currentDatasets.length === 1">
              {{ turncateString(currentDatasets[0].name || currentDatasets[0].id, 12) }}
            </strong>
            <strong v-else>
              {{ currentDatasets.length }} 个
            </strong>
          </template>
          <el-link v-else type="warning" @click="goToAddData" :underline="false">
            请先选择一个数据集进行分析
          </el-link>
        </div>
      </el-tooltip>

      <!-- MCP 连接指示器 -->
      <el-tooltip placement="top" :content="formatMCPTooltip(mcpConnections || [])">
        <div class="mcp-indicator">
          <el-icon>
            <Link />
          </el-icon>
          <template v-if="mcpConnections?.length">
            MCP 连接:
            <strong>
              {{ mcpConnections.length }} 个
            </strong>
            <div class="mcp-tags" v-if="mcpConnections.length > 0">
              <el-tag
                v-for="connection in mcpConnections.slice(0, 3)"
                :key="connection.id"
                :type="getTransportTagType(connection.connection.transport)"
                size="small"
                style="margin-left: 4px;">
                {{ turncateString(connection.name, 8) }}
              </el-tag>
              <el-tag v-if="mcpConnections.length > 3" size="small" style="margin-left: 4px;">
                +{{ mcpConnections.length - 3 }}
              </el-tag>
            </div>
          </template>
          <span v-else class="no-mcp">
            无 MCP 连接
          </span>
        </div>
      </el-tooltip>

      <el-divider direction="vertical" style="margin: 0 8px;" />
      <div class="quick-prompt-tags">
        <el-tag v-for="(question, index) in quickQuestions" :key="index" class="action-tag"
          @click="input = question.prompt">
          <el-icon>
            <component :is="question.icon" />
          </el-icon>
          {{ question.text }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.chat-input-area {
  padding: 12px 20px 6px;
  background-color: #ffffff;
  border-top: 1px solid #e5e7eb;
}

.chat-input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  margin-bottom: 12px;

  .el-textarea {
    flex: 1;
  }

  .send-button {
    flex-shrink: 0;
    height: 32px;
    padding: 0 16px;
  }
}

.quick-actions {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  padding: 12px 16px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.dataset-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
  padding: 4px 8px;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;

  .el-icon {
    font-size: 14px;
  }

  strong {
    color: #374151;
  }
}

.mcp-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
  padding: 4px 8px;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e5e7eb;

  .el-icon {
    font-size: 14px;
  }

  strong {
    color: #374151;
  }

  .no-mcp {
    color: #9ca3af;
    font-style: italic;
  }

  .mcp-tags {
    display: flex;
    align-items: center;
    margin-left: 4px;
  }

  .el-link {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: 8px;
    font-size: 12px;

    .el-icon {
      font-size: 12px;
    }
  }
}

.quick-prompt-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.action-tag {
  cursor: pointer;
  transition: all 0.2s ease;
  background-color: #ffffff;
  color: #6b7280;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;

  .el-icon {
    font-size: 12px;
  }

  &:hover {
    background-color: #f3f4f6;
    color: #374151;
    border-color: #d1d5db;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .chat-input-area {
    padding: 12px 16px 16px;
  }

  .quick-actions {
    justify-content: flex-start;
  }

  .dataset-indicator {
    margin-right: 8px;
    margin-bottom: 8px;
  }
}
</style>
