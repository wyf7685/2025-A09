<template>
  <div class="loading-container" v-if="visible">
    <div class="loading-overlay" :class="{ fullscreen: fullscreen }">
      <div class="loading-content">
        <el-icon class="loading-icon" :size="size">
          <Loading />
        </el-icon>
        <div class="loading-text" v-if="text">{{ text }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Loading } from '@element-plus/icons-vue'

defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  text: {
    type: String,
    default: ''
  },
  size: {
    type: Number,
    default: 48
  },
  fullscreen: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped lang="scss">
.loading-container {
  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255, 255, 255, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;

    &.fullscreen {
      position: fixed;
      z-index: 9999;
      background: rgba(0, 0, 0, 0.5);
    }

    .loading-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;

      .loading-icon {
        color: var(--el-color-primary);
        animation: rotate 2s linear infinite;
      }

      .loading-text {
        color: #606266;
        font-size: 14px;
      }
    }
  }
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
