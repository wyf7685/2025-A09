"""
自定义模型管理器
管理用户自定义的API模型配置
"""

from typing import Any

from pydantic import TypeAdapter

from app.const import DATA_DIR
from app.core.lifespan import lifespan
from app.log import logger
from app.schemas.custom_model import CustomModelConfig

_models_ta = TypeAdapter(dict[str, CustomModelConfig])


class CustomModelManager:
    """自定义模型管理器"""

    def __init__(self) -> None:
        self._models: dict[str, CustomModelConfig] = {}
        self.config_file = DATA_DIR / "custom_models.json"
        self.config_file.parent.mkdir(exist_ok=True)

    def _load_config(self) -> None:
        """加载自定义模型配置"""
        if self.config_file.exists():
            try:
                data = _models_ta.validate_json(self.config_file.read_bytes())
                self._models.update(data)
                logger.info(f"已加载自定义模型配置: {len(self._models)} 个模型")
            except Exception as e:
                logger.warning(f"加载自定义模型配置失败: {e}")
                self._models = {}

    def _save_config(self) -> None:
        """保存自定义模型配置"""
        try:
            self.config_file.write_bytes(_models_ta.dump_json(self._models))
            logger.debug("自定义模型配置已保存")
        except Exception as e:
            logger.error(f"保存自定义模型配置失败: {e}")

    def add_model(self, config: CustomModelConfig) -> None:
        """添加自定义模型配置"""
        self._models[config.id] = config
        self._save_config()
        logger.info(f"添加自定义模型: {config.name} ({config.id})")

    def get_model(self, model_id: str) -> CustomModelConfig | None:
        """获取自定义模型配置"""
        return self._models.get(model_id)

    def remove_model(self, model_id: str) -> bool:
        """移除自定义模型配置"""
        if model_id in self._models:
            del self._models[model_id]
            self._save_config()
            logger.info(f"移除自定义模型: {model_id}")
            return True
        return False

    def list_models(self) -> dict[str, CustomModelConfig]:
        """列出所有自定义模型"""
        return self._models.copy()

    def is_custom_model(self, model_id: str) -> bool:
        """检查是否是自定义模型"""
        return model_id in self._models

    def update_model(self, model_id: str, **kwargs: Any) -> bool:
        """更新自定义模型配置"""
        if model_id not in self._models:
            return False

        model = self._models[model_id]
        for key, value in kwargs.items():
            if hasattr(model, key):
                setattr(model, key, value)

        self._save_config()
        logger.info(f"更新自定义模型: {model_id}")
        return True


# 全局自定义模型管理器实例
custom_model_manager = CustomModelManager()
lifespan.on_startup(custom_model_manager._load_config)  # noqa: SLF001
