import json
import re

from pydantic import BaseModel

from app.core.agent.prompts.clean_data import PROMPTS
from app.core.chain import get_llm
from app.log import logger

from .schemas import CleaningState, load_source


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
    return PROMPTS.field_mapping.format(
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
