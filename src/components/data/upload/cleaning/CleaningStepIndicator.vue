<script setup lang="ts">
import type { CleaningStep } from '@/types/cleaning';
import { Icon } from '@iconify/vue';

// 组件属性
defineProps<{
  currentStep: CleaningStep;
}>();

// 步骤配置
const steps = [
  { key: 'upload', name: '文件上传', icon: 'mdi:cloud-upload' },
  { key: 'analysis', name: '智能分析', icon: 'material-symbols:analytics-outline-rounded' },
  { key: 'cleaning', name: '清洗建议', icon: 'material-symbols:cleaning-services-outline-rounded' },
  { key: 'complete', name: '完成上传', icon: 'material-symbols:check-circle-outline-rounded' },
] as { key: CleaningStep, name: string, icon: string; }[];

// 获取步骤索引
const getStepIndex = (step: CleaningStep) => {
  return steps.findIndex(s => s.key === step);
};
</script>

<template>
  <div class="cleaning-steps">
    <div class="step" v-for="stepItem in steps" :key="stepItem.key" :class="{
      active: currentStep === stepItem.key,
      completed: getStepIndex(currentStep) > getStepIndex(stepItem.key)
    }">
      <div class="step-icon">
        <template v-if="getStepIndex(currentStep) > getStepIndex(stepItem.key)">
          <Icon :icon="'material-symbols:check-circle-rounded'" width="24" height="24" color="#67C23A" />
        </template>
        <template v-else-if="currentStep === stepItem.key">
          <Icon :icon="stepItem.icon" width="24" height="24" color="#409EFF" />
        </template>
        <template v-else>
          <Icon :icon="stepItem.icon" width="24" height="24" color="#C0C4CC" />
        </template>
      </div>
      <div class="step-title">{{ stepItem.name }}</div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.cleaning-steps {
  display: flex;
  justify-content: space-between;
  margin-bottom: 32px;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    top: 20px;
    left: 20px;
    right: 20px;
    height: 2px;
    background: #e5e7eb;
    z-index: 1;
  }

  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
    flex: 1;
    z-index: 2;

    .step-icon {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: #f3f4f6;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 8px;
      transition: all 0.3s ease;

      .el-icon {
        font-size: 20px;
        color: #9ca3af;
      }
    }

    .step-title {
      font-size: 12px;
      color: #6b7280;
      text-align: center;
      font-weight: 500;
    }

    &.active {
      .step-icon {
        background: #3b82f6;

        .el-icon {
          color: white;
        }
      }

      .step-title {
        color: #3b82f6;
        font-weight: 600;
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .cleaning-steps {
    flex-wrap: wrap;
    gap: 12px;

    &::before {
      display: none;
    }

    .step {
      flex-basis: calc(50% - 6px);
      margin-bottom: 12px;
    }
  }
}
</style>
