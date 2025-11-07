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
  result?: unknown;
  artifact?: ToolCallArtifact | null; // 工具调用的工件
  error?: string; // 错误信息，如果有的话
  flowStepId?: string; // 对应的流程图步骤ID
}

export interface UserChatMessage {
  type: 'user';
  content: string;
  timestamp: string;
}

export interface AssistantChatMessageText {
  type: 'text';
  content: string;
}

export interface AssistantChatMessageToolCall {
  type: 'tool_call';
  id: string; // 工具调用的唯一标识符
}

export type AssistantChatMessageContent = AssistantChatMessageText | AssistantChatMessageToolCall;

export interface AssistantChatMessage {
  type: 'assistant';
  content: AssistantChatMessageContent[];
  timestamp: string;
  tool_calls?: Record<string, ToolCall>;
}

/**
 * 聊天消息
 */
export type ChatMessage = UserChatMessage | AssistantChatMessage;
