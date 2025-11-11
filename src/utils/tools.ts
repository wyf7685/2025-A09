import { marked } from 'marked';
// import hljs from 'highlight.js';
import 'github-markdown-css/github-markdown-light.css'; // 导入 GitHub 风格样式
import 'highlight.js/styles/github.css'; // 导入 GitHub 代码高亮样式
import { computed, ref, type Ref, type WritableComputedRef } from 'vue';
import { ElMessage } from 'element-plus';

// 配置 marked 使用 highlight.js 进行代码高亮
marked.setOptions({
  // highlight: function (code: string, lang: string) {
  //   if (lang && hljs.getLanguage(lang)) {
  //     return hljs.highlight(code, { language: lang }).value;
  //   }
  //   return hljs.highlightAuto(code).value;
  // },
  gfm: true, // 启用 GitHub 风格 Markdown
  breaks: true, // 将换行符转换为 <br>
});

/**
 * 将 Markdown 文本转换为 HTML
 * @param text Markdown 文本
 * @returns 格式化的 HTML 字符串
 */
export const formatMessage = async (text?: string): Promise<string> => {
  if (!text) return '';

  // 处理特殊语法并转换为 HTML
  const html = marked.parse(text);

  return html || '';
};

export const turncateString = (str: string, maxLength: number): string => {
  if (str.length <= maxLength) {
    return str;
  }
  return str.slice(0, maxLength) + '...';
};

export const parsePossibleJsonString = (value: unknown) => {
  if (typeof value !== 'string') return value;

  try {
    const obj = JSON.parse(value);
    return JSON.stringify(obj, null, 2);
  } catch (error: unknown) {
    console.log('parsePossibleJsonString error:', error);
    return value;
  }
};

export const base64ToBlob = (b64_data: string, contentType: string = ''): Blob | null => {
  // 检查 b64_data 是否以 "data:" 开头，如果是，则提取实际的 Base64 数据和 MIME 类型
  let base64String = b64_data;
  let mimeType = contentType;

  if (b64_data.startsWith('data:')) {
    const parts = b64_data.split(',');
    if (parts.length > 1) {
      // 提取 MIME 类型，例如 "image/png"
      const meta = parts[0].split(';')[0].split(':')[1];
      if (meta) {
        mimeType = meta;
      }
      // 提取实际的 Base64 数据
      base64String = parts[1];
    }
  }

  // 检查是否成功提取了 MIME 类型，如果没有，则尝试从 b64_data 中推断
  if (!mimeType) {
    // 这是一个简单的推断，可能不适用于所有情况
    if (base64String.startsWith('/9j/')) {
      mimeType = 'image/jpeg';
    } else if (base64String.startsWith('iVBORw0KGgo')) {
      mimeType = 'image/png';
    } else if (base64String.startsWith('R0lGODlh')) {
      mimeType = 'image/gif';
    } else {
      console.warn('无法从 Base64 数据中推断 MIME 类型');
      return null;
    }
  }

  return new Blob([Uint8Array.from(atob(base64String), (c) => c.charCodeAt(0))], {
    type: mimeType,
  });
};

export function withLoading<T>(ref: Ref<boolean>, proceed: () => T | Promise<T>): Promise<T>;
export function withLoading<T>(
  ref: Ref<boolean>,
  proceed: () => T | Promise<T>,
  onerror: string,
): Promise<T | null>;
export function withLoading<T, E>(
  ref: Ref<boolean>,
  proceed: () => T | Promise<T>,
  onerror: (error: unknown) => E | Promise<E>,
): Promise<T | E>;
export async function withLoading<T, E>(
  ref: Ref<boolean>,
  proceed: () => T | Promise<T>,
  onerror?: string | ((error: unknown) => E | Promise<E>),
): Promise<T | E | null> {
  ref.value = true;
  try {
    return await proceed();
  } catch (error: unknown) {
    if (onerror === undefined) throw error;
    if (typeof onerror === 'string') {
      console.error(`${onerror}: ${error}`);
      ElMessage.error(onerror);
      return null;
    } else {
      return await onerror(error);
    }
  } finally {
    ref.value = false;
  }
}

export const sleep = async (ms: number) => {
  await new Promise((resolve) => setTimeout(resolve, ms));
};

export const persistConfig = <T>(key: string, defaultValue: T): WritableComputedRef<T> => {
  const storedValue = localStorage.getItem(key);
  const data = ref(storedValue ? JSON.parse(storedValue) : defaultValue);

  return computed<T>({
    get() {
      return data.value;
    },
    set(newValue: T) {
      data.value = newValue;
      localStorage.setItem(key, JSON.stringify(newValue));
    },
  });
};
