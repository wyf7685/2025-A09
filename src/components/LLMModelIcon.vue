<script setup lang="ts">
import DeepseekIcon from '@/assets/icons/deepseek.ico';
import ZhipuAIIcon from '@/assets/icons/zhipu.svg';
import { Icon } from '@iconify/vue';

defineProps<{
  provider: string;
  size: number;
}>();

const standardIcons = {
  'OpenAI': { icon: 'simple-icons:openai', color: '#00a67e' },
  'Google': { icon: 'logos:google-icon', color: '#4285f4' },
  'Anthropic': { icon: 'simple-icons:anthropic', color: '#d97706' },
  'Ollama': { icon: 'simple-icons:ollama', color: '#000000' },
} as Record<string, { icon: string, color: string; }>;

const extraIcons = {
  'DeepSeek': DeepseekIcon,
  'ZhipuAI': ZhipuAIIcon,
} as Record<string, string>;
</script>

<template>
  <img v-if="extraIcons[provider]"
    :src="extraIcons[provider]"
    :alt="provider"
    :width="size"
    :height="size"
    style="border-radius: 4px;" />
  <Icon v-else-if="standardIcons[provider]"
    :icon="standardIcons[provider].icon"
    :width="size"
    :height="size"
    :color="standardIcons[provider].color" />
  <Icon v-else
    icon="material-symbols:settings-outline"
    :width="size"
    :height="size"
    color="#6b7280" />
</template>
