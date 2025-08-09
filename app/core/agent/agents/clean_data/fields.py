import json
import re

from pydantic import BaseModel

from app.core.chain import get_llm
from app.log import logger

from .schemas import CleaningState, load_source

PROMPT_FIELD_MAPPING = """
你是一位专业的数据分析师，擅长理解数据结构和字段含义。
请分析以下数据集的字段，并为每个字段提供标准化的名称和描述。

字段信息:
{columns_info}

数据样本:
{sample_data}

用户要求:
{user_requirements}

请为每个字段提供以下信息，以JSON格式返回:
{{
  "field_mappings": [
    {{
      "original_name": "原始字段名",
      "suggested_name": "建议的标准字段名",
      "confidence": 0.95,
      "field_type": "字段类型(如: 数值型、文本型、日期型等)",
      "description": "字段含义的详细描述"
    }}
  ]
}}

要求:
1. 建议的字段名应该简洁、清晰、符合命名规范
2. 置信度应该基于数据样本的清晰程度
3. 字段类型要准确反映数据的实际类型
4. 描述要详细说明字段的业务含义
"""


def create_field_mapping_prompt(state: CleaningState) -> str:
    """创建字段映射提示词"""
    df = load_source(state, "source_id").get_full()
    columns_info = [
        {
            "original_name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isna().sum()),
            "unique_count": int(df[col].nunique()),
            "sample_values": df[col].dropna().head(3).tolist(),
        }
        for col in df.columns
    ]
    return PROMPT_FIELD_MAPPING.format(
        columns_info=json.dumps(columns_info, ensure_ascii=False, indent=2),
        sample_data=json.dumps(df.head(5).to_dict("records"), ensure_ascii=False, indent=2),
        user_requirements=state.get("user_requirements") or "无特殊要求",
    )


class LLMFieldMappingResponse(BaseModel):
    """LLM返回的字段映射响应模型"""

    class FieldMapping(BaseModel):
        """单个字段映射"""

        original_name: str
        suggested_name: str
        confidence: float
        field_type: str
        description: str

    field_mappings: list[FieldMapping] = []


def parse_field_mappings(response: str) -> dict[str, str]:
    """解析LLM返回的字段映射"""
    try:
        # 尝试提取JSON部分
        if not (json_match := re.search(r"\{.*\}", response, re.DOTALL)):
            logger.warning("无法从LLM响应中提取JSON格式的字段映射")
            return {}

        parsed = LLMFieldMappingResponse.model_validate_json(json_match.group(0))

        return {
            original: suggested
            for mapping in parsed.field_mappings
            if (original := mapping.original_name) and (suggested := mapping.suggested_name)
        }

    except Exception as e:
        logger.error(f"解析字段映射失败: {e}")
        return {}


def guess_field_names(state: CleaningState) -> CleaningState:
    """使用LLM猜测数据源字段名"""
    try:
        logger.info("开始猜测字段名")
        chain = create_field_mapping_prompt | get_llm() | parse_field_mappings
        field_mappings = chain.invoke(state)
        state["field_mappings"] = field_mappings
        logger.info(f"字段名猜测完成，处理了 {len(field_mappings)} 个字段")
        return state

    except Exception as e:
        logger.error(f"字段名猜测失败: {e}")
        state["error_message"] = str(e)
        return state
