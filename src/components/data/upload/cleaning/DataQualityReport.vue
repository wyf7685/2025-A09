<script setup lang="ts">
import type { DataQualityReport } from '@/types/cleaning';
import { ElButton, ElCollapseTransition, ElDescriptions, ElDescriptionsItem } from 'element-plus';
import { ref } from 'vue';

// 定义组件属性
defineProps<{
  dataQualityReport: DataQualityReport | null;
}
>();

// 详情显示状态
const showDetails = ref(false);

const formatValue = (value: unknown): string => {
  if (typeof value === 'number') {
    return value.toFixed(2);
  } else if (typeof value === 'boolean') {
    return value ? '是' : '否';
  } else if (Array.isArray(value)) {
    return value.map(item => formatValue(item)).join(' ');
  } else if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
};
</script>

<template>
  <div class="detailed-quality-report">
    <div class="section-header">
      <h4>详细质量报告</h4>
      <el-button type="text" @click="showDetails = !showDetails">
        {{ showDetails ? '收起详情' : '查看详情' }}
      </el-button>
    </div>

    <el-collapse-transition>
      <div v-show="showDetails" class="report-details">
        <el-descriptions :column="2" border>
          <el-descriptions-item v-for="(value, key) in dataQualityReport" :key="key" :label="key">
            <span>{{ formatValue(value) }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-collapse-transition>
  </div>
</template>

<style lang="scss" scoped>
.detailed-quality-report {
  margin-bottom: 24px;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    h4 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: #1f2937;
    }
  }

  .report-details {
    background: white;
    padding: 16px;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
  }
}
</style>
