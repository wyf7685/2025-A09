<template>
  <div class="process-flow">
    <div class="flow-header">
      <h3>处理流程</h3>
      <el-button 
        type="text" 
        size="small" 
        @click="clearFlow"
        :disabled="flowSteps.length === 0"
      >
        清空
      </el-button>
    </div>
    
    <div class="flow-content">
      <div v-if="flowSteps.length === 0" class="empty-flow">
        <el-empty description="暂无处理流程" :image-size="60" />
      </div>
      
      <div v-else class="flow-steps">
        <div 
          v-for="(step, index) in flowSteps" 
          :key="index"
          :class="['flow-step', { 
            'active': step.status === 'running',
            'completed': step.status === 'completed',
            'error': step.status === 'error'
          }]"
        >
          <div class="step-header">
            <div class="step-icon">
              <el-icon v-if="step.status === 'running'">
                <Loading />
              </el-icon>
              <el-icon v-else-if="step.status === 'completed'">
                <CircleCheck />
              </el-icon>
              <el-icon v-else-if="step.status === 'error'">
                <CircleClose />
              </el-icon>
              <el-icon v-else>
                <CircleCheckFilled />
              </el-icon>
            </div>
            <div class="step-info">
              <div class="step-title">{{ step.title }}</div>
              <div class="step-time">{{ formatTime(step.timestamp) }}</div>
            </div>
          </div>
          
          <!-- 步骤描述 - 支持折叠 -->
          <div v-if="step.description" class="step-description">
            <div 
              :class="['description-content', { 'collapsed': !expandedDescriptions[index] }]"
              :ref="el => setDescriptionRef(el, index)"
            >
              {{ step.description }}
            </div>
            <el-button 
              v-if="descriptionNeedsCollapse[index]"
              type="text" 
              size="small" 
              @click="toggleDescription(index)"
              class="collapse-btn"
            >
              {{ expandedDescriptions[index] ? '收起' : '展开' }}
              <el-icon class="collapse-icon">
                <ArrowDown v-if="!expandedDescriptions[index]" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
          </div>
          
          <!-- 步骤详情 - 支持折叠 -->
          <div v-if="step.details && step.details.length > 0" class="step-details">
            <div 
              :class="['details-content', { 'collapsed': !expandedDetails[index] }]"
              :ref="el => setDetailsRef(el, index)"
            >
              <div 
                v-for="(detail, detailIndex) in step.details" 
                :key="detailIndex"
                class="step-detail"
              >
                <el-icon class="detail-icon">
                  <InfoFilled />
                </el-icon>
                <span>{{ detail }}</span>
              </div>
            </div>
            <el-button 
              v-if="detailsNeedCollapse[index]"
              type="text" 
              size="small" 
              @click="toggleDetails(index)"
              class="collapse-btn"
            >
              {{ expandedDetails[index] ? '收起' : '展开' }}
              <el-icon class="collapse-icon">
                <ArrowDown v-if="!expandedDetails[index]" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
          </div>
          
          <!-- 步骤错误 - 支持折叠 -->
          <div v-if="step.error" class="step-error">
            <div 
              :class="['error-content', { 'collapsed': !expandedErrors[index] }]"
              :ref="el => setErrorRef(el, index)"
            >
              <el-icon class="error-icon">
                <Warning />
              </el-icon>
              <span>{{ step.error }}</span>
            </div>
            <el-button 
              v-if="errorsNeedCollapse[index]"
              type="text" 
              size="small" 
              @click="toggleError(index)"
              class="collapse-btn error-collapse-btn"
            >
              {{ expandedErrors[index] ? '收起' : '展开' }}
              <el-icon class="collapse-icon">
                <ArrowDown v-if="!expandedErrors[index]" />
                <ArrowUp v-else />
              </el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { 
  Loading, 
  CircleCheck, 
  CircleClose, 
  CircleCheckFilled,
  InfoFilled,
  Warning,
  ArrowDown,
  ArrowUp
} from '@element-plus/icons-vue'

export interface FlowStep {
  id: string
  title: string
  description?: string
  status: 'pending' | 'running' | 'completed' | 'error'
  timestamp: Date
  details?: string[]
  error?: string
}

const props = defineProps<{
  steps?: FlowStep[]
}>()

const emit = defineEmits<{
  clear: []
}>()

const flowSteps = computed(() => props.steps || [])

// 折叠状态管理
const expandedDescriptions = ref<boolean[]>([])
const expandedDetails = ref<boolean[]>([])
const expandedErrors = ref<boolean[]>([])

// 是否需要折叠的判断
const descriptionNeedsCollapse = ref<boolean[]>([])
const detailsNeedCollapse = ref<boolean[]>([])
const errorsNeedCollapse = ref<boolean[]>([])

// 元素引用
const descriptionRefs = ref<HTMLElement[]>([])
const detailsRefs = ref<HTMLElement[]>([])
const errorRefs = ref<HTMLElement[]>([])

const formatTime = (timestamp: Date) => {
  return timestamp.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const clearFlow = () => {
  emit('clear')
}

// 设置元素引用
const setDescriptionRef = (el: HTMLElement | null, index: number) => {
  if (el) {
    descriptionRefs.value[index] = el
  }
}

const setDetailsRef = (el: HTMLElement | null, index: number) => {
  if (el) {
    detailsRefs.value[index] = el
  }
}

const setErrorRef = (el: HTMLElement | null, index: number) => {
  if (el) {
    errorRefs.value[index] = el
  }
}

// 切换折叠状态
const toggleDescription = (index: number) => {
  expandedDescriptions.value[index] = !expandedDescriptions.value[index]
}

const toggleDetails = (index: number) => {
  expandedDetails.value[index] = !expandedDetails.value[index]
}

const toggleError = (index: number) => {
  expandedErrors.value[index] = !expandedErrors.value[index]
}

// 检查内容是否需要折叠
const checkCollapseNeeded = () => {
  nextTick(() => {
    // 检查描述是否需要折叠
    descriptionRefs.value.forEach((el, index) => {
      if (el) {
        const lineHeight = parseInt(getComputedStyle(el).lineHeight)
        const maxHeight = lineHeight * 2 // 最多显示2行
        descriptionNeedsCollapse.value[index] = el.scrollHeight > maxHeight
      }
    })

    // 检查详情是否需要折叠
    detailsRefs.value.forEach((el, index) => {
      if (el) {
        const maxHeight = 120 // 最多显示120px高度
        detailsNeedCollapse.value[index] = el.scrollHeight > maxHeight
      }
    })

    // 检查错误是否需要折叠
    errorRefs.value.forEach((el, index) => {
      if (el) {
        const lineHeight = parseInt(getComputedStyle(el).lineHeight)
        const maxHeight = lineHeight * 3 // 最多显示3行
        errorsNeedCollapse.value[index] = el.scrollHeight > maxHeight
      }
    })
  })
}

// 监听步骤变化，重新检查折叠状态
watch(() => props.steps, () => {
  nextTick(() => {
    // 重置折叠状态
    const stepsLength = flowSteps.value.length
    expandedDescriptions.value = new Array(stepsLength).fill(false)
    expandedDetails.value = new Array(stepsLength).fill(false)
    expandedErrors.value = new Array(stepsLength).fill(false)
    
    descriptionNeedsCollapse.value = new Array(stepsLength).fill(false)
    detailsNeedCollapse.value = new Array(stepsLength).fill(false)
    errorsNeedCollapse.value = new Array(stepsLength).fill(false)
    
    // 清空引用数组
    descriptionRefs.value = []
    detailsRefs.value = []
    errorRefs.value = []
    
    // 检查折叠状态
    setTimeout(checkCollapseNeeded, 100)
  })
}, { deep: true })

onMounted(() => {
  checkCollapseNeeded()
})
</script>

<style lang="scss" scoped>
.process-flow {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: white;
  border-left: 1px solid #e5e7eb;
}

.flow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #374151;
  }
}

.flow-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-flow {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9ca3af;
}

.flow-steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.flow-step {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  transition: all 0.3s ease;

  &.active {
    border-color: #3b82f6;
    background: #eff6ff;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  &.completed {
    border-color: #10b981;
    background: #f0fdf4;
  }

  &.error {
    border-color: #ef4444;
    background: #fef2f2;
  }
}

.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.step-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: white;
  border: 2px solid #d1d5db;

  .el-icon {
    font-size: 14px;
    color: #6b7280;
  }
}

.flow-step.active .step-icon {
  border-color: #3b82f6;
  background: #3b82f6;

  .el-icon {
    color: white;
  }
}

.flow-step.completed .step-icon {
  border-color: #10b981;
  background: #10b981;

  .el-icon {
    color: white;
  }
}

.flow-step.error .step-icon {
  border-color: #ef4444;
  background: #ef4444;

  .el-icon {
    color: white;
  }
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 600;
  color: #374151;
  margin-bottom: 2px;
}

.step-time {
  font-size: 12px;
  color: #6b7280;
}

.step-description {
  margin-bottom: 8px;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.5;

  .description-content {
    transition: max-height 0.3s ease;
    overflow: hidden;

    &.collapsed {
      max-height: 2.5em; // 约2行高度
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }
  }
}

.step-details {
  margin-bottom: 8px;

  .details-content {
    transition: max-height 0.3s ease;
    overflow: hidden;

    &.collapsed {
      max-height: 120px;
    }
  }
}

.step-detail {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 13px;
  color: #6b7280;

  .detail-icon {
    font-size: 12px;
    color: #9ca3af;
  }
}

.step-error {
  .error-content {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 8px;
    background: #fef2f2;
    border-radius: 4px;
    border: 1px solid #fecaca;
    color: #dc2626;
    font-size: 13px;
    transition: max-height 0.3s ease;
    overflow: hidden;

    &.collapsed {
      max-height: 4.5em; // 约3行高度
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
    }

    .error-icon {
      font-size: 14px;
      margin-top: 1px;
      flex-shrink: 0;
    }
  }
}

.collapse-btn {
  margin-top: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: #6b7280;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: color 0.2s ease;

  &:hover {
    color: #374151;
  }

  .collapse-icon {
    font-size: 10px;
    transition: transform 0.2s ease;
  }

  &.error-collapse-btn {
    color: #dc2626;

    &:hover {
      color: #b91c1c;
    }
  }
}

// 滚动条样式
.flow-content::-webkit-scrollbar {
  width: 6px;
}

.flow-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.flow-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.flow-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style> 