from pydantic import BaseModel

type LLModelID = str


class CustomModelConfig(BaseModel):
    """自定义模型配置"""

    id: LLModelID
    name: str
    provider: str
    api_url: str
    api_key: str
    model_name: str  # 实际调用的模型名称
