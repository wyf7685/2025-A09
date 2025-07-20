export interface ReportTemplate {
  id: string; // 模板唯一标识符
  name: string; // 模板名称
  description: string; // 模板描述
  content: string; // 模板内容
  is_default: boolean; // 是否为默认模板
  created_at: string; // 创建时间
}
