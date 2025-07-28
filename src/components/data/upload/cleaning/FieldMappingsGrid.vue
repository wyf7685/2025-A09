<script setup lang="ts">
import { ArrowRight } from '@element-plus/icons-vue';
import { ElIcon, ElTag } from 'element-plus';

// 定义组件属性
defineProps<{
  fieldMappings: Record<string, string>;
}>();
</script>

<template>
  <div v-if="Object.keys(fieldMappings).length > 0" class="field-mappings-section">
    <div class="section-header">
      <h4>字段理解与映射建议</h4>
      <el-tag type="info">{{ Object.keys(fieldMappings).length }} 个字段</el-tag>
    </div>

    <div class="mappings-grid">
      <div v-for="(suggestion, originalName) in fieldMappings" :key="originalName" class="mapping-card">
        <div class="mapping-header">
          <div class="original-field">
            <el-tag type="info" size="small">原始字段</el-tag>
            <span class="field-name" :title="originalName">{{ originalName }}</span>
          </div>
          <div class="mapping-arrow">
            <el-icon class="arrow-icon">
              <ArrowRight />
            </el-icon>
          </div>
          <div class="suggested-field">
            <el-tag type="success" size="small">标准字段</el-tag>
            <span class="field-name" :title="suggestion">{{ suggestion }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.field-mappings-section {
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

  .mappings-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 300px;
    overflow-y: auto;
    padding-right: 8px;

    .mapping-card {
      padding: 16px;
      background: white;
      border-radius: 8px;
      border: 1px solid #e5e7eb;
      transition: all 0.2s ease;

      &:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        border-color: #d1d5db;
      }

      .mapping-header {
        display: flex;
        align-items: center;

        .original-field,
        .suggested-field {
          display: flex;
          align-items: center;
          gap: 8px;
          flex: 1;

          .field-name {
            font-weight: 500;
            color: #374151;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 200px;
          }
        }

        .mapping-arrow {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 40px;
          flex-shrink: 0;

          .arrow-icon {
            color: #6366f1;
            font-size: 20px;
          }
        }
      }
    }
  }
}
</style>
