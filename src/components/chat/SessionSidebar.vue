<script setup lang="ts">
import { useSessionStore } from '@/stores/session';
import { ChatDotRound, DArrowLeft, Delete, Edit, Plus } from '@element-plus/icons-vue';
import { ElButton, ElIcon } from 'element-plus';
import { computed, ref } from 'vue';
import MCPManager from './MCPManager.vue';
import type { MCPConnection } from '@/types/mcp';

const isSidebarOpen = defineModel<boolean>('isSidebarOpen', { required: true });
const sessionMCPConnections = defineModel<MCPConnection[]>('sessionMCPConnections', { required: true });

const emit = defineEmits<{
  'switch-session': [sessionId: string];                    // 切换会话
  'create-session': [];                                     // 创建新会话
  'edit-session': [sessionId: string, sessionName: string]; // 编辑会话
  'delete-session': [sessionId: string];                    // 删除会话
}>();

const sessionStore = useSessionStore();
const sessions = computed(() => sessionStore.sessions);
const currentSessionId = computed(() => sessionStore.currentSessionId);
const isDeletingSession = ref<boolean>(false); // 防止重复删除操作

// 处理侧边栏关闭
const closeSidebar = () => {
  isSidebarOpen.value = false;
};

// 切换会话
const handleSwitchSession = (sessionId: string) => {
  emit('switch-session', sessionId);
};

// 创建新会话
const handleCreateSession = () => {
  emit('create-session');
};

// 编辑会话
const handleEditSession = (sessionId: string, sessionName: string, event: Event) => {
  event.stopPropagation(); // 阻止触发会话切换
  emit('edit-session', sessionId, sessionName);
};

// 处理删除会话，同时暴露MCP管理器的引用
const handleDeleteSession = async (sessionId: string, event: Event) => {
  // 阻止事件冒泡，避免触发会话切换
  event.stopPropagation();

  // 防止重复操作
  if (isDeletingSession.value) return;
  isDeletingSession.value = true;

  try {
    emit('delete-session', sessionId);
  } finally {
    isDeletingSession.value = false;
  }
};
</script>

<template>
  <div :class="['session-sidebar', { 'is-closed': !isSidebarOpen }]">
    <div class="sidebar-header">
      <el-button class="new-chat-btn" @click="handleCreateSession" :icon="Plus">
        新对话
      </el-button>
      <el-button @click="closeSidebar" :icon="DArrowLeft" text class="toggle-btn" />
    </div>
    <div class="session-list">
      <div v-for="session in sessions" :key="session.id"
        :class="['session-item', { active: session.id === currentSessionId }]" @click="handleSwitchSession(session.id)">
        <el-icon class="session-icon">
          <ChatDotRound />
        </el-icon>
        <span class="session-name">{{ session.name || `会话 ${session.id.slice(0, 8)}` }}</span>
        <div class="session-actions">
          <el-button type="text" :icon="Edit" size="small" class="action-btn"
            @click.stop="handleEditSession(session.id, session.name || `会话 ${session.id.slice(0, 8)}`, $event)" />
          <el-button type="text" :icon="Delete" size="small" class="action-btn"
            @click.stop="handleDeleteSession(session.id, $event)" :loading="sessionStore.isDeleting[session.id]"
            :disabled="sessionStore.isDeleting[session.id]" />
        </div>
      </div>
    </div>

    <!-- MCP 管理器 -->
    <div class="mcp-section" v-if="currentSessionId">
      <MCPManager v-model:sessionMCPConnections="sessionMCPConnections" />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.session-sidebar {
  width: 240px;
  flex-shrink: 0;
  background-color: #ffffff;
  color: #374151;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  overflow: hidden;
  border-right: 1px solid #e5e7eb;

  &.is-closed {
    width: 0;
  }
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  flex-shrink: 0;
  border-bottom: 1px solid #e5e7eb;
}

.new-chat-btn {
  flex-grow: 1;
  margin-right: 8px;
  background-color: transparent;
  border: 1px solid #d1d5db;
  color: #374151;
  justify-content: flex-start;
  border-radius: 8px;
  font-weight: 500;
  padding: 8px 12px;
  transition: all 0.2s ease;

  &:hover {
    background-color: #f3f4f6;
    border-color: #9ca3af;
  }

  &:focus {
    border-color: #10b981;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
  }
}

.toggle-btn {
  color: #6b7280;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s ease;

  &:hover {
    color: #374151;
    background-color: #f3f4f6;
  }
}

.session-list {
  flex-grow: 1;
  overflow-y: auto;
  padding: 8px 12px;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;

    &:hover {
      background: #a8a8a8;
    }
  }
}

.session-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  color: #374151;
  font-weight: 500;

  .session-icon {
    margin-right: 12px;
    color: #6b7280;
    font-size: 16px;
  }

  .session-name {
    flex-grow: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 14px;
  }

  .session-actions {
    display: none;
    align-items: center;
    gap: 4px;

    .action-btn {
      color: #9ca3af;
      padding: 4px;
      border-radius: 4px;
      transition: all 0.2s ease;

      &:hover {
        color: #374151;
        background-color: #f3f4f6;
      }

      &.delete-btn:hover {
        color: #ef4444;
        background-color: #fef2f2;
      }
    }
  }

  &:hover {
    background-color: #f9fafb;

    .session-icon {
      color: #374151;
    }

    .session-actions {
      display: flex;
    }
  }

  &.active {
    background-color: #f3f4f6;
    color: #10b981;

    .session-icon {
      color: #10b981;
    }

    &:hover {
      background-color: #f3f4f6;
    }
  }
}

.mcp-section {
  flex-shrink: 0;
  padding: 12px;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .session-sidebar {
    width: 100%;
    max-height: 200px;
    border-right: none;
    border-bottom: 1px solid #e5e7eb;

    &.is-closed {
      max-height: 0;
      overflow: hidden;
    }
  }
}
</style>
