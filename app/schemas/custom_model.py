from pydantic import BaseModel

type LLModelID = str


class CustomModelConfig(BaseModel):
    """自定义模型配置"""

    id: LLModelID
    name: str
    provider: str
    api_url: str
    api_key: str
    model_name: str  # 用户自定义的显示名称
    api_model_name: str  # API调用时使用的正确模型名称
