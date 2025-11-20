<script setup lang="ts">
import DeepseekIcon from '@/assets/icons/deepseek.ico';
import ZhipuAIIcon from '@/assets/icons/zhipu.svg';
import type { FunctionalComponent } from 'vue';
import LogosGoogleIcon from '~icons/logos/google-icon';
import SimpleIconsAnthropic from '~icons/simple-icons/anthropic';
import SimpleIconsOllama from '~icons/simple-icons/ollama';
import SimpleIconsOpenai from '~icons/simple-icons/openai';
import StreamlineLogosOpenaiLogo from '~icons/streamline-logos/openai-logo';

defineProps<{
  provider: string;
  size: number;
}>();

const standardIcons = {
  'OpenAI': { icon: SimpleIconsOpenai, color: '#00a67e' },
  'Google': { icon: LogosGoogleIcon, color: '#4285f4' },
  'Anthropic': { icon: SimpleIconsAnthropic, color: '#d97706' },
  'Ollama': { icon: SimpleIconsOllama, color: '#000000' },
  'OpenAI兼容': { icon: StreamlineLogosOpenaiLogo, color: '#6366f1' },
  'OpenAI-Compat': {
    icon: StreamlineLogosOpenaiLogo, color: '#6366f1'
  },
} as Record<string, { icon: FunctionalComponent, color: string; }>;

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
  <component v-else-if="standardIcons[provider]"
    :is="standardIcons[provider].icon"
    :width="size"
    :height="size"
    :color="standardIcons[provider].color" />
  <i-material-symbols-settings-outline v-else
    :width="size"
    :height="size"
    color="#6b7280" />
</template>
