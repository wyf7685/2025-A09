/**
 * 聊天条目
 */
export interface ChatEntry {
  timestamp: string;
  user_message: UserChatMessage;
  assistant_response: AssistantChatMessage;
}

export interface ToolCallArtifact {
  type: 'image'; // 当前仅包含图片
  base64_data: string;
  caption?: string; // 可选的图像说明
}

export interface ToolCall {
  name: string;
  args: string;
  status: 'running' | 'success' | 'error';
  result?: any;
  artifact?: ToolCallArtifact | null; // 工具调用的工件
  error?: string; // 错误信息，如果有的话
}

export interface UserChatMessage {
  type: 'user';
  content: string;
  timestamp: string;
}

export interface AssistantChatMessage {
  type: 'assistant';
  content: ({ type: 'text'; content: string } | { type: 'tool_call'; id: string })[];
  timestamp: string;
  tool_calls?: Record<string, ToolCall>;
}

/**
 * 聊天消息
 */
export type ChatMessage = UserChatMessage | AssistantChatMessage;
