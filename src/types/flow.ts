import type { Ref } from 'vue';

// 流程图步骤类型定义
export interface FlowStep {
  id: string;
  title: string;
  description?: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  timestamp: Date;
  details?: string[];
  error?: string;
}

export interface FlowRoute {
  title: string;
  description: string;
  status: 'pending' | 'active' | 'completed' | 'error';
  nextLoop?: FlowRoute[];
  toolName?: string;
  selectedModel?: string; // 每个流程节点可以选择自己的LLM模型
}

export interface FlowPanel {
  route1Steps: Ref<FlowRoute[]>;
  route2Steps: Ref<FlowRoute[]>;
  selectedModel: Ref<string>;
  clearFlowSteps: () => void;
  updateRouteStep: (stepIndex: number, status: 'pending' | 'active' | 'completed') => void;
  autoSelectRoute: (userMessage: string) => 'route1' | 'route2';
  logRouteStatus: (message: string) => void;
  getActiveStepModel: () => string; // 获取当前活动步骤的模型ID
}
