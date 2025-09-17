<script setup lang="ts">
import { useModelStore } from '@/stores/model';
import { useSessionStore } from '@/stores/session';
import type { FlowPanel, FlowStep, LLMModel } from '@/types';
import { CircleCheck, Clock, DArrowRight, Loading, Monitor, Setting } from '@element-plus/icons-vue';
import {
  ElButton, ElDialog, ElForm, ElFormItem, ElIcon, ElInput, ElMessage,
  ElOption, ElOptionGroup, ElSelect, ElText
} from 'element-plus';
import { computed, onMounted, ref } from 'vue';

// 扩展 FlowRoute 类型，支持 nextLoop 和 toolName 字段
type FlowRouteEx = {
  title: string;
  description: string;
  status: 'pending' | 'active' | 'completed' | 'error';
  nextLoop?: FlowRouteEx[];
  toolName?: string;
  _needLoop?: boolean;
};

const modelStore = useModelStore();
const sessionStore = useSessionStore();

// 控制流程图面板的显示/隐藏
const isFlowPanelOpen = defineModel<boolean>("isFlowPanelOpen", { required: true });

// 固定路线配置
const selectedRoute = ref<string>('route1'); // 当前选中的路线
const currentRouteReason = ref<string>(''); // 当前路线选择的原因

// 路线1：生成总体报告的步骤
const route1Steps = ref<FlowRouteEx[]>([
  { title: '用户输入', description: '接收用户的查询请求', status: 'pending' },
  { title: 'API请求处理', description: '后端API接收并处理请求', status: 'pending' },
  { title: 'LLM模型选择', description: '选择适合的AI模型处理', status: 'pending' },
  { title: 'Agent初始化', description: '初始化数据分析Agent', status: 'pending' },
  { title: '生成分析报告', description: '生成完整的数据分析结果', status: 'pending' }
]);

// 路线2：其他处理的步骤
const route2Steps = ref<FlowRouteEx[]>([
  { title: '用户输入', description: '接收用户的查询请求', status: 'pending', toolName: '' },
  { title: 'API请求处理', description: '后端API接收并处理请求', status: 'pending', toolName: '' },
  { title: 'LLM模型选择', description: '选择适合的AI模型处理', status: 'pending', toolName: '' },
  { title: '数据源加载', description: '读取和解析数据源', status: 'pending', toolName: '' },
  { title: '工具调用', description: '执行相应的数据处理工具', status: 'pending', toolName: '' },
  { title: '是否进行循环', description: '判断是否需要继续处理', status: 'pending', nextLoop: [], toolName: '' }
]);

// 流程图相关状态 (保留原有的flowSteps以兼容现有代码)
const flowSteps = ref<FlowStep[]>([]);

// 模型配置相关状态
const storeAvailableModels = computed(() => modelStore.availableModels);

// 自定义API相关状态
const showCustomApiDialog = ref(false);
const customApiForm = ref({
  provider: '',  // 选择的提供商
  apiKey: '',
  modelName: '',
  customApiUrl: ''  // 自定义API URL
});

// 调试函数：监控流程图状态
const logRouteStatus = (message: string) => {
  console.log(`[流程图调试] ${message}`);
  console.log('当前路线:', selectedRoute.value);
  if (selectedRoute.value === 'route1') {
    console.log('路线1状态:', route1Steps.value.map((step: FlowRouteEx) => `${step.title}: ${step.status}`));
  } else {
    console.log('路线2状态:', route2Steps.value.map((step: FlowRouteEx) => `${step.title}: ${step.status}`));
  }
};

// 检查是否有活跃步骤
const hasActiveSteps = computed(() => {
  if (selectedRoute.value === 'route1') {
    return route1Steps.value.some((step: FlowRouteEx) => step.status === 'active');
  } else {
    return route2Steps.value.some((step: FlowRouteEx) => step.status === 'active');
  }
});

// 强制完成流程
const forceCompleteFlow = () => {
  console.log('用户强制完成流程');

  if (selectedRoute.value === 'route1') {
    route1Steps.value.forEach((step: FlowRouteEx) => {
      if (step.status === 'active' || step.status === 'pending') {
        step.status = 'completed';
      }
    });
  } else {
    route2Steps.value.forEach((step: FlowRouteEx) => {
      if (step.status === 'active' || step.status === 'pending') {
        step.status = 'completed';
      }
    });
  }

  logRouteStatus('用户强制完成所有流程步骤');
  ElMessage.success('流程已强制完成');
};

// 只显示已执行的步骤（直接暴露给模板）
// 动态流程节点，支持循环追加
const executedSteps = computed(() => {
  if (selectedRoute.value === 'route1') {
    // 只显示已执行的步骤
    return route1Steps.value.filter(step => step.status !== 'pending');
  } else {
    // 路线2支持循环追加
    const steps = [];
    for (let i = 0; i < route2Steps.value.length; i++) {
      const step = route2Steps.value[i];
      if (step.status !== 'pending') {
        // 判断是否进行循环节点特殊处理
        if (step.title === '是否进行循环') {
          // 没有调用新工具时，nextLoop为空，显示"否"且不追加新节点
          steps.push({
            ...step,
            nextLoop: [], // 保证模板判断为否
          });
          // 只有在 nextLoop 节点已被激活或完成时追加新工具节点
          if (
            step.nextLoop &&
            step.nextLoop.length > 0 &&
            ['active', 'completed', 'error'].includes(step.nextLoop[0].status)
          ) {
            steps.push(...step.nextLoop);
          }
        } else {
          steps.push(step);
        }
      }
    }
    return steps;
  }
});

// 预设的API提供商配置
const apiProviders = [
  {
    name: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    models: ['gpt-4', 'gpt-3.5-turbo', 'gpt-4-turbo']
  },
  {
    name: 'Google',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    models: ['gemini-2.0-flash', 'gemini-1.5-pro']
  },
  {
    name: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com/v1',
    models: ['deepseek-chat', 'deepseek-coder']
  },
  {
    name: 'Anthropic',
    baseUrl: 'https://api.anthropic.com/v1',
    models: ['claude-3-sonnet', 'claude-3-opus', 'claude-3-haiku']
  },
  {
    name: 'Custom',
    baseUrl: '',
    models: []
  }
];

const selectedProvider = computed(() => {
  return apiProviders.find(p => p.name === customApiForm.value.provider) || apiProviders[0];
});

const providerModels = computed(() => {
  return selectedProvider.value.models;
});

const selectedModel = computed({
  get: () => modelStore.selectedModel?.id || 'gemini-2.0-flash',
  set: (value: string) => {
    if (value === 'custom-api') {
      // 显示自定义API对话框
      showCustomApiDialog.value = true;
      return;
    }
    const model = storeAvailableModels.value.find(m => m.id === value);
    if (model) {
      modelStore.setSelectedModel(model);
    }
  }
});

// 流程图管理方法
const addFlowStep = (step: Omit<FlowStep, 'id' | 'timestamp'>) => {
  const newStep: FlowStep = {
    ...step,
    id: `step-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    timestamp: new Date()
  };
  flowSteps.value.push(newStep);
  return newStep.id;
};

const updateFlowStep = (stepId: string, updates: Partial<FlowStep>) => {
  const stepIndex = flowSteps.value.findIndex(step => step.id === stepId);
  if (stepIndex !== -1) {
    flowSteps.value[stepIndex] = { ...flowSteps.value[stepIndex], ...updates };
  }
};

const clearFlowSteps = () => {
  // 清除旧的流程步骤
  flowSteps.value = [];

  // 完全重置路线1步骤状态
  route1Steps.value = [
    { title: '用户输入', description: '接收用户的查询请求', status: 'pending' },
    { title: 'API请求处理', description: '后端API接收并处理请求', status: 'pending' },
    { title: 'LLM模型选择', description: '选择适合的AI模型处理', status: 'pending' },
    { title: 'Agent初始化', description: '初始化数据分析Agent', status: 'pending' },
    { title: '生成分析报告', description: '生成完整的数据分析结果', status: 'pending' }
  ];

  // 完全重置路线2步骤状态
  route2Steps.value = [
    { title: '用户输入', description: '接收用户的查询请求', status: 'pending', toolName: '' },
    { title: 'API请求处理', description: '后端API接收并处理请求', status: 'pending', toolName: '' },
    { title: 'LLM模型选择', description: '选择适合的AI模型处理', status: 'pending', toolName: '' },
    { title: '数据源加载', description: '读取和解析数据源', status: 'pending', toolName: '' },
    { title: '工具调用', description: '执行相应的数据处理工具', status: 'pending', toolName: '' },
    { title: '是否进行循环', description: '判断是否需要继续处理', status: 'pending', nextLoop: [], toolName: '' }
  ];

  console.log('[流程图] 已完全重置所有流程步骤');
};

// 模型配置方法
const changeModel = async (modelId: string) => {
  if (modelId === 'custom-api') {
    // 显示自定义API对话框
    showCustomApiDialog.value = true;
    return;
  }

  selectedModel.value = modelId;
  await sessionStore.updateSessionAgentModelConfig({ default: modelId });
  const model = storeAvailableModels.value.find(m => m.id === modelId);

  // 添加模型切换步骤到流程图
  addFlowStep({
    title: '模型切换',
    description: `切换到模型: ${model?.name || modelId}`,
    status: 'completed'
  });

  ElMessage.success(`已切换到模型: ${model?.name || modelId}`);
};

// 处理自定义API配置
const handleCustomApiSubmit = async () => {
  if (!customApiForm.value.provider || !customApiForm.value.apiKey || !customApiForm.value.modelName) {
    ElMessage.error('请填写完整的API信息');
    return;
  }

  try {
    const provider = selectedProvider.value;
    let apiUrl = provider.baseUrl;

    // 如果是自定义提供商，使用用户输入的URL
    if (customApiForm.value.provider === 'Custom') {
      apiUrl = customApiForm.value.customApiUrl;
      if (!apiUrl) {
        ElMessage.error('请输入自定义API URL');
        return;
      }
    }

    console.log('发送的数据:', {
      name: customApiForm.value.modelName,
      provider: customApiForm.value.provider,
      api_url: apiUrl,
      api_key: customApiForm.value.apiKey,
      model_name: customApiForm.value.modelName
    });

    // 调用后端API保存自定义模型配置
    const customModel = await modelStore.submitCustomModel({
      name: customApiForm.value.modelName,
      provider: customApiForm.value.provider,
      api_url: apiUrl,
      api_key: customApiForm.value.apiKey,
      model_name: customApiForm.value.modelName
    });

    showCustomApiDialog.value = false;

    // 重置表单
    customApiForm.value = {
      provider: '',
      apiKey: '',
      modelName: '',
      customApiUrl: ''
    };

    // 添加模型切换步骤到流程图
    addFlowStep({
      title: '自定义模型配置',
      description: `配置自定义模型: ${customModel.name}`,
      status: 'completed'
    });

    ElMessage.success(`已配置自定义模型: ${customModel.name}`);
  } catch (error) {
    console.error('配置自定义API失败:', error);
    ElMessage.error('配置自定义API失败');
  }
};

const cancelCustomApi = () => {
  showCustomApiDialog.value = false;
  // 重置表单
  customApiForm.value = {
    provider: '',
    apiKey: '',
    modelName: '',
    customApiUrl: ''
  };
};

const getCurrentModelInfo = computed(() => {
  return modelStore.selectedModel || storeAvailableModels.value[0] || { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', provider: 'Google' };
});

// 按提供商分组模型
const getProviderGroups = () => {
  const groups: { name: string; models: LLMModel[]; }[] = [];
  const providers = new Set(storeAvailableModels.value.map(m => m.provider));

  providers.forEach(provider => {
    const models = storeAvailableModels.value.filter(m => m.provider === provider);
    groups.push({
      name: provider,
      models: models
    });
  });

  return groups;
};

// 路线切换处理
const handleRouteChange = (route: string) => {
  console.log('切换到路线:', route);
  logRouteStatus(`切换到${route}`);
  // 重置所有步骤状态
  resetAllSteps();
  logRouteStatus('重置步骤状态完成');
};

// 重置所有路线步骤状态
const resetAllSteps = () => {
  route1Steps.value.forEach((step: FlowRouteEx) => {
    step.status = 'pending';
  });
  route2Steps.value.forEach((step: FlowRouteEx) => {
    step.status = 'pending';
  });
};

// 更新当前路线的步骤状态
const updateRouteStep = (stepIndex: number, status: 'pending' | 'active' | 'completed') => {
  const oldStatus = selectedRoute.value === 'route1'
    ? route1Steps.value[stepIndex]?.status
    : route2Steps.value[stepIndex]?.status;

  if (selectedRoute.value === 'route1' && route1Steps.value[stepIndex]) {
    route1Steps.value[stepIndex].status = status;
    console.log(`[流程图] 路线1步骤${stepIndex + 1}状态更新: ${oldStatus} -> ${status}`);
  } else if (selectedRoute.value === 'route2' && route2Steps.value[stepIndex]) {
    // 允许 updateRouteStep 控制 nextLoop 节点状态
    if (stepIndex === 4 && route2Steps.value[5]?.nextLoop && route2Steps.value[5].nextLoop.length > 0) {
      // 旧节点强制 completed
      route2Steps.value[stepIndex].status = 'completed';
    } else if (stepIndex === 5 && route2Steps.value[stepIndex].nextLoop && route2Steps.value[stepIndex].nextLoop.length > 0) {
      // 如果是"是否进行循环"节点，允许通过 status 控制 nextLoop 节点状态
      // 只更新 nextLoop 的第一个节点（即新追加的调用工具节点）
      route2Steps.value[stepIndex].nextLoop[0].status = status;
    } else {
      route2Steps.value[stepIndex].status = status;
    }
    console.log(`[流程图] 路线2步骤${stepIndex + 1}状态更新: ${oldStatus} -> ${route2Steps.value[stepIndex].status}`);

    // 如果是"是否进行循环"节点且完成判断
    if (route2Steps.value[stepIndex].title === '是否进行循环' && status === 'completed') {
      // 检查是否需要继续循环 (根据nextLoop的标记来判断)
      const needLoop = route2Steps.value[stepIndex].hasOwnProperty('_needLoop') ?
        route2Steps.value[stepIndex]._needLoop : false;

      // 只有当明确需要循环时，才追加循环节点
      if (needLoop) {
        // 只追加一次循环节点，且工具名与左侧对话栏一致
        if (!route2Steps.value[stepIndex].nextLoop || route2Steps.value[stepIndex].nextLoop.length === 0) {
          let toolName = route2Steps.value[4]?.toolName;

          // 旧的工具调用节点直接设为 completed
          if (route2Steps.value[4]) {
            route2Steps.value[4].status = 'completed';
          }
          // 追加新的循环节点，反映工具运行状况（只有新节点显示 active）
          route2Steps.value[stepIndex].nextLoop = [
            {
              title: '工具调用',
              description: `执行新的数据处理工具（循环）`,
              status: 'active',
              toolName: toolName
            }
          ];
        } else {
          // 如果已存在循环节点，确保旧节点不是 active
          if (route2Steps.value[4] && route2Steps.value[4].status === 'active') {
            route2Steps.value[4].status = 'completed';
          }
        }
      } else {
        // 如果不需要循环，确保nextLoop为空数组
        route2Steps.value[stepIndex].nextLoop = [];
        console.log('[流程图] 循环判断结果为"否"，不生成新工具调用流程');
      }
    }

    // 如果所有对话已完成，则将所有流程节点状态设为 completed
    // 这里假设对话完成时会调用 updateRouteStep 并传入 status = 'completed'
    if (status === 'completed') {
      if (selectedRoute.value === 'route2') {
        // 主流程节点
        route2Steps.value.forEach((step: FlowRouteEx) => {
          if (step.status === 'active') step.status = 'completed';
        });
        // 循环追加的节点
        route2Steps.value.forEach((step: FlowRouteEx) => {
          if (step.nextLoop && step.nextLoop.length > 0) {
            step.nextLoop.forEach((loopStep: FlowRouteEx) => {
              if (loopStep.status === 'active') loopStep.status = 'completed';
            });
          }
        });
      }
    }
  }

  logRouteStatus(`步骤${stepIndex + 1}状态更新为${status}`);
};

// 测试智能路线选择功能
const testRouteSelection = () => {
  const testCases = [
    "生成完整报告",
    "创建数据分析报告",
    "给我一个综合分析",
    "绘制相关性热力图",
    "计算统计信息",
    "分析数据质量"
  ];

  console.log('=== 智能路线选择测试 ===');
  testCases.forEach(testCase => {
    const route = selectRouteAutomatically(testCase);
    const reason = getRouteSelectionReason(testCase, route);
    console.log(`输入: "${testCase}" -> 路线: ${route} (${reason})`);
  });
  console.log('=== 测试完成 ===');
};

// 智能路线选择函数
const selectRouteAutomatically = (userMessage: string): 'route1' | 'route2' => {
  const message = userMessage.toLowerCase();

  // 路线1关键词：综合分析相关
  const route1Keywords = [
    '报告', '总结', '概述', '汇总', '分析报告', '数据报告',
    '整体分析', '全面分析', '综合分析', '统计报告',
    '生成报告', '创建报告', '制作报告', '输出报告',
    '完整报告', '详细报告', '综合报告', '总体报告',
    '分析结果', '数据总结', '统计总结', '整体情况',
    '基本情况', '基本统计', '基础分析', '数据概况',
    'report', 'summary', 'overview', 'analysis report',
    'comprehensive', 'complete report', 'detailed report'
  ];

  // 路线2关键词：工具调用相关
  const route2Keywords = [
    '绘制', '画图', '图表', '可视化', '图像', '图片',
    '计算', '统计', '筛选', '过滤', '查询', '搜索',
    '清洗', '处理', '转换', '操作', '执行', '运行',
    '热力图', '散点图', '柱状图', '折线图', '饼图',
    '分组', '聚合', '相关性', '异常检测', '缺失值',
    '预测', '分类', '回归', '聚类', '预处理',
    'plot', 'chart', 'graph', 'visualization', 'draw',
    'calculate', 'filter', 'query', 'clean', 'process'
  ];

  // 检查是否包含路线1关键词
  const hasRoute1Keywords = route1Keywords.some(keyword => message.includes(keyword));

  // 检查是否包含路线2关键词
  const hasRoute2Keywords = route2Keywords.some(keyword => message.includes(keyword));

  // 决策逻辑
  if (hasRoute1Keywords && !hasRoute2Keywords) {
    return 'route1';
  } else if (hasRoute2Keywords && !hasRoute1Keywords) {
    return 'route2';
  } else if (hasRoute1Keywords && hasRoute2Keywords) {
    // 如果同时包含，根据优先级判断
    // 如果明确提到"报告"，优先选择路线1
    if (message.includes('报告') || message.includes('report')) {
      return 'route1';
    }
    return 'route2';
  } else {
    // 默认情况：如果都不包含特定关键词，根据消息长度和复杂度判断
    // 简短的问题通常是具体操作，长的问题通常需要综合分析
    if (message.length > 100 || message.includes('分析') || message.includes('怎么') || message.includes('如何')) {
      return 'route1';
    }
    return 'route2';
  }
};

// 获取路线选择的原因说明
const getRouteSelectionReason = (userMessage: string, selectedRoute: 'route1' | 'route2'): string => {
  const message = userMessage.toLowerCase();

  if (selectedRoute === 'route1') {
    if (message.includes('报告') || message.includes('report')) {
      return '检测到综合报告需求，将进行完整数据分析';
    } else if (message.includes('分析') || message.includes('总结') || message.includes('概述')) {
      return '检测到数据概览分析需求，将选择适合的模型处理';
    } else if (message.includes('基本') || message.includes('基础') || message.includes('统计')) {
      return '检测到基础统计分析需求';
    } else if (message.length > 100) {
      return '复杂查询，适合完整的Agent处理链';
    } else {
      return '默认使用完整分析流程';
    }
  } else {
    if (message.includes('绘制') || message.includes('图表') || message.includes('可视化')) {
      return '检测到数据可视化需求，准备调用相关工具';
    } else if (message.includes('计算') || message.includes('统计') || message.includes('筛选')) {
      return '检测到数据处理需求，准备调用数据工具';
    } else if (message.includes('热力图') || message.includes('散点图') || message.includes('柱状图')) {
      return '检测到特定图表需求，准备加载数据源';
    } else if (message.includes('分组') || message.includes('聚合') || message.includes('相关性')) {
      return '检测到高级数据分析需求';
    } else {
      return '检测到特定操作需求，准备选择合适的工具';
    }
  }
};

// 自动路线选择并更新UI
const autoSelectRoute = (userMessage: string) => {
  const previousRoute = selectedRoute.value;
  const newRoute = selectRouteAutomatically(userMessage);
  const reason = getRouteSelectionReason(userMessage, newRoute);

  currentRouteReason.value = reason;

  if (newRoute !== previousRoute) {
    selectedRoute.value = newRoute;
    resetAllSteps();
    logRouteStatus(`自动切换路线：${previousRoute} -> ${newRoute} (${reason})`);
    console.log(`[智能路线选择] 用户输入: "${userMessage}"`);
    console.log(`[智能路线选择] 选择路线: ${newRoute}`);
    console.log(`[智能路线选择] 选择原因: ${reason}`);
  } else {
    logRouteStatus(`保持当前路线: ${newRoute} (${reason})`);
  }

  return newRoute;
};

// 手动切换路线
const toggleRouteManually = () => {
  const currentRoute = selectedRoute.value;
  const newRoute = currentRoute === 'route1' ? 'route2' : 'route1';

  selectedRoute.value = newRoute;
  resetAllSteps();

  console.log(`[手动路线切换] ${currentRoute} -> ${newRoute}`);
  logRouteStatus(`手动切换路线到: ${newRoute}`);

  ElMessage.info(`已手动切换到路线: ${newRoute === 'route1' ? '生成总体报告' : '调用工具分析'}`);
};

defineExpose({
  flowPanel: {
    route1Steps,
    route2Steps,
    selectedModel,
    clearFlowSteps,
    updateRouteStep,
    autoSelectRoute,
    logRouteStatus,
  } as FlowPanel,
});

// --- Lifecycle Hooks ---
onMounted(async () => {
  await modelStore.fetchAvailableModels(); // 获取可用模型

  // 运行路线选择测试
  // testRouteSelection()

  // 初始化模型配置
  addFlowStep({
    title: '系统初始化',
    description: `默认模型已设置为 ${getCurrentModelInfo.value.name}`,
    status: 'completed',
    details: [
      `模型: ${getCurrentModelInfo.value.name}`,
      `提供商: ${getCurrentModelInfo.value.provider}`,
      `模型ID: ${selectedModel.value}`
    ]
  });
});
</script>

<template>
  <div :class="['flow-panel', { 'is-closed': !isFlowPanelOpen }]">
    <div class="flow-panel-header">
      <span class="panel-title">
        <el-icon>
          <Monitor />
        </el-icon>
        处理流程
      </span>
      <div class="header-actions">
        <el-button @click="forceCompleteFlow" size="small" type="text" class="force-complete-btn" title="强制完成流程"
          v-if="hasActiveSteps">
          完成
        </el-button>
        <el-button @click="isFlowPanelOpen = false" :icon="DArrowRight" text size="small" class="toggle-btn" />
      </div>
    </div>

    <!-- 模型配置区域 -->
    <div class="model-config-section">
      <div class="config-header">
        <span class="config-title">
          <el-icon>
            <Setting />
          </el-icon>
          模型配置
        </span>
      </div>
      <div class="model-selector">
        <el-select v-model="selectedModel" @change="changeModel" placeholder="选择模型" size="small" class="model-select">
          <!-- 按提供商分组显示模型 -->
          <el-option-group v-for="provider in getProviderGroups()" :key="provider.name" :label="provider.name">
            <el-option v-for="model in provider.models" :key="model.id"
              :label="model.name" :value="model.id">
              <div class="model-option">
                <span class="model-name">{{ model.name }}</span>
                <span v-if="!model.available" class="model-status">(未配置)</span>
              </div>
            </el-option>
          </el-option-group>
          <el-option-group label="自定义">
            <el-option label="输入API" value="custom-api">
              <div class="model-option">
                <span class="model-name">输入API</span>
              </div>
            </el-option>
          </el-option-group>
        </el-select>
      </div>
      <div class="current-model-info">
        <span class="current-model">
          当前: {{ getCurrentModelInfo.name }}
        </span>
      </div>
    </div>

    <div class="flow-panel-content">
      <div class="fixed-flow-routes">
        <!-- 只显示当前运行的流程步骤 -->

        <!-- Dify风格流程图：卡片+连线 -->
        <!-- Dify风格流程图：默认空，执行时动态添加节点 -->
        <div class="dify-flow">
          <div class="dify-flow-steps">
            <template v-for="(step, index) in executedSteps" :key="index">
              <div :class="['dify-step-card', step.status]">
                <div class="dify-step-title">{{ step.title }}</div>
                <div class="dify-step-desc">
                  {{ step.description }}
                  <template v-if="step.title === '是否进行循环'">
                    <span style="color:#10b981;font-size:13px;font-weight:600;display:block;margin-top:2px;">
                      循环：{{ step.nextLoop && step.nextLoop.length > 0 ? '是' : '否' }}
                    </span>
                  </template>
                  <span v-if="step.toolName"
                    style="color:#3b82f6;font-size:12px;font-weight:500;display:block;margin-top:2px;">
                    {{ (selectedRoute === 'route2' && step.title === '工具调用') ? '工具：' + step.toolName :
                      (step.title === 'LLM模型选择') ? '模型：' + step.toolName :
                        step.toolName }}
                  </span>
                </div>
                <div class="dify-step-status">
                  <el-icon v-if="step.status === 'active'" class="loading">
                    <Loading />
                  </el-icon>
                  <el-icon v-else-if="step.status === 'completed'" class="completed">
                    <CircleCheck />
                  </el-icon>
                  <el-icon v-else class="pending">
                    <Clock />
                  </el-icon>
                </div>
              </div>
              <svg v-if="index < executedSteps.length - 1" class="dify-flow-line" width="40" height="40">
                <line x1="20" y1="0" x2="20" y2="40" stroke="#3b82f6" stroke-width="2" />
              </svg>
            </template>
            <!-- 无已执行步骤时不显示任何内容 -->
            <template v-if="executedSteps.length === 0"></template>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 自定义API配置对话框 -->
  <el-dialog v-model="showCustomApiDialog" title="配置自定义API" width="500px" :before-close="cancelCustomApi">
    <el-form :model="customApiForm" label-width="120px">
      <el-form-item label="API提供商" required>
        <el-select v-model="customApiForm.provider" placeholder="选择API提供商" style="width: 100%">
          <el-option v-for="provider in apiProviders" :key="provider.name" :label="provider.name"
            :value="provider.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="API Key" required>
        <el-input v-model="customApiForm.apiKey" type="password" placeholder="请输入API密钥" show-password clearable />
      </el-form-item>
      <el-form-item label="模型名称" required>
        <el-select v-if="providerModels.length > 0" v-model="customApiForm.modelName" placeholder="选择模型"
          style="width: 100%" filterable allow-create>
          <el-option v-for="model in providerModels" :key="model" :label="model" :value="model" />
        </el-select>
        <el-input v-else v-model="customApiForm.modelName" placeholder="输入模型名称" clearable />
      </el-form-item>

      <!-- 自定义API URL输入 (仅当选择Custom提供商时显示) -->
      <el-form-item v-if="customApiForm.provider === 'Custom'" label="API URL" required>
        <el-input v-model="customApiForm.customApiUrl" placeholder="例如: https://api.example.com/v1" clearable />
      </el-form-item>

      <div v-if="selectedProvider.baseUrl" class="api-info">
        <el-text type="info">API地址: {{ selectedProvider.baseUrl }}</el-text>
      </div>
      <div v-else-if="customApiForm.provider === 'Custom'" class="api-info">
        <el-text type="warning">请输入自定义API URL</el-text>
      </div>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="cancelCustomApi">取消</el-button>
        <el-button type="primary" @click="handleCustomApiSubmit">确定</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
// Dify风格流程图样式
.dify-flow {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 24px 0;
}

.dify-flow-steps {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.dify-step-card {
  background: #fff;
  border: 2px solid #3b82f6;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.08);
  padding: 16px 24px;
  margin: 0 0 0 0;
  min-width: 180px;
  max-width: 260px;
  text-align: center;
  position: relative;
  z-index: 1;
  transition: border-color 0.2s;
}

.dify-step-card.pending {
  border-color: #9ca3af;
}

.dify-step-card.active {
  border-color: #3b82f6;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.15);
}

.dify-step-card.completed {
  border-color: #10b981;
}

.dify-step-title {
  font-size: 15px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 6px;
}

.dify-step-desc {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
}

.dify-step-status {
  margin-top: 4px;

  .el-icon {
    font-size: 18px;
    vertical-align: middle;

    &.loading {
      color: #3b82f6;
      animation: rotating 1s linear infinite;
    }

    &.completed {
      color: #10b981;
    }

    &.pending {
      color: #9ca3af;
    }
  }
}

.dify-flow-line {
  display: block;
  margin: -8px 0 0 0;
  z-index: 0;
}

// --- Flow Panel Styles ---
.flow-panel {
  width: 320px;
  flex-shrink: 0;
  background: #ffffff;
  border-left: 1px solid #e5e7eb;
  transition: width 0.3s ease;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  &.is-closed {
    width: 0;
  }
}

.flow-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
  flex-shrink: 0;

  .panel-title {
    display: flex;
    align-items: center;
    gap: 4px;
    font-weight: 600;
    color: #374151;
    font-size: 12px;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .force-complete-btn {
    color: #f59e0b;
    padding: 2px 6px;
    font-size: 10px;

    &:hover {
      color: #d97706;
      background-color: #fef3c7;
    }
  }

  .toggle-btn {
    color: #6b7280;
    padding: 2px;
    border-radius: 3px;
    transition: all 0.2s ease;

    &:hover {
      color: #374151;
      background-color: #e5e7eb;
    }
  }
}

.flow-panel-content {
  flex: 1;
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

// --- Model Config Styles ---
.model-config-section {
  padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;

  .config-header {
    margin-bottom: 8px;

    .config-title {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      font-weight: 600;
      color: #374151;
    }
  }

  .model-selector {
    margin-bottom: 6px;

    .model-select {
      width: 100%;

      :deep(.el-input) {
        height: 28px;

        .el-input__inner {
          font-size: 11px;
          height: 28px;
          line-height: 28px;
          padding: 0 8px;
        }
      }

      :deep(.el-select__popper) {
        .el-option-group__title {
          font-size: 10px;
          padding: 4px 8px;
          color: #6b7280;
          font-weight: 600;
        }
      }
    }
  }

  .model-option {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;

    .model-name {
      font-size: 11px;
      color: #374151;
      flex: 1;
    }

    .model-provider {
      font-size: 9px;
      color: #9ca3af;
      background: #f3f4f6;
      padding: 1px 4px;
      border-radius: 3px;
      margin-left: 8px;
    }

    .model-status {
      font-size: 9px;
      color: #ef4444;
      font-style: italic;
    }
  }

  .current-model-info {
    .current-model {
      font-size: 10px;
      color: #10b981;
      font-weight: 500;
      background: #f0fdf4;
      padding: 2px 6px;
      border-radius: 3px;
      border: 1px solid #bbf7d0;
      display: inline-block;
      width: 100%;
      text-align: center;
    }
  }
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.5);
  }

  70% {
    box-shadow: 0 0 0 5px rgba(59, 130, 246, 0);
  }

  100% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
  }
}

/* 自定义API对话框样式 */
.api-info {
  margin-top: 10px;
  font-size: 12px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
