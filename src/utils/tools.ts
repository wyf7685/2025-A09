import { marked } from 'marked';
// import hljs from 'highlight.js';
import 'github-markdown-css/github-markdown-light.css'; // 导入 GitHub 风格样式
import 'highlight.js/styles/github.css'; // 导入 GitHub 代码高亮样式

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
