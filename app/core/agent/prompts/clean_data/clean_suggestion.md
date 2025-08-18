基于用户的清洗要求，为以下数据集生成具体的清洗建议。

数据概览:
{data_overview}

用户要求:
{user_requirements}

请生成清洗建议，以JSON格式返回:
{{
  "suggestions": [
    {{
      "column": "列名",
      "issue_type": "问题类型",
      "description": "问题描述",
      "suggested_action": "建议的清洗动作",
      "priority": "优先级(high/medium/low)",
      "parameters": {{"参数名": "参数值"}},
      "auto_apply": false
    }}
  ]
}}

要求:
1. 建议要具体、可执行
2. 优先级要合理
3. 参数要完整
4. 只有安全的操作才设置auto_apply为true
