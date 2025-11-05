from pydantic import BaseModel

type LLModelID = str


class CustomModelConfig(BaseModel):
    """自定义模型完整配置（包含敏感信息）"""

    id: LLModelID
    name: str
    provider: str
    api_url: str
    api_key: str
    model_name: str  # 用户自定义的显示名称
    api_model_name: str  # API调用时使用的正确模型名称


class CustomModelInfo(BaseModel):
    """自定义模型信息（不包含敏感信息，用于API返回）"""

    id: LLModelID
    name: str
    provider: str
    api_url: str
    model_name: str
    api_model_name: str
