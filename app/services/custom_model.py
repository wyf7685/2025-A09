"""
自定义模型管理器
管理用户自定义的API模型配置
"""

from pydantic import BaseModel

from app.log import logger


class CustomModelConfig(BaseModel):
    """自定义模型配置"""

    id: str
    name: str
    provider: str
    api_url: str
    api_key: str
    model_name: str  # 实际调用的模型名称


class CustomModelManager:
    """自定义模型管理器"""

    def __init__(self) -> None:
        self._models: dict[str, CustomModelConfig] = {}

    def add_model(self, config: CustomModelConfig) -> None:
        """添加自定义模型配置"""
        self._models[config.id] = config
        logger.info(f"添加自定义模型: {config.name} ({config.id})")

    def get_model(self, model_id: str) -> CustomModelConfig | None:
        """获取自定义模型配置"""
        return self._models.get(model_id)

    def remove_model(self, model_id: str) -> bool:
        """移除自定义模型配置"""
        if model_id in self._models:
            del self._models[model_id]
            logger.info(f"移除自定义模型: {model_id}")
            return True
        return False

    def list_models(self) -> dict[str, CustomModelConfig]:
        """列出所有自定义模型"""
        return self._models.copy()

    def is_custom_model(self, model_id: str) -> bool:
        """检查是否是自定义模型"""
        return model_id in self._models


# 全局自定义模型管理器实例
custom_model_manager = CustomModelManager()
