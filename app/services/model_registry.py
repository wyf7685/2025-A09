"""
模型注册表 - 统一管理所有训练好的模型
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from app.const import DATA_DIR, MODEL_DIR
from app.log import logger
from app.schemas.ml_model import MLModelInfo

_models_ta = TypeAdapter(dict[str, MLModelInfo])

class ModelRegistry:
    """模型注册表"""

    def __init__(self) -> None:
        self.models_dir = MODEL_DIR
        self.registry_file = DATA_DIR / "model_registry.json"
        self.models_dir.mkdir(exist_ok=True)
        self._models: dict[str, MLModelInfo] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """加载模型注册表"""
        if self.registry_file.exists():
            try:
                data = _models_ta.validate_json(self.registry_file.read_bytes())
                self._models.update(data)
                logger.info(f"已加载模型注册表: {len(self._models)} 个模型")
            except Exception as e:
                logger.warning(f"加载模型注册表失败: {e}")
                self._models = {}

    def _save_registry(self) -> None:
        """保存模型注册表"""
        try:
            self.registry_file.write_bytes(_models_ta.dump_json(self._models))
            logger.debug("模型注册表已保存")
        except Exception as e:
            logger.error(f"保存模型注册表失败: {e}")

    def register_model(
        self,
        name: str,
        model_type: str,
        session_id: str,
        dataset_id: str,
        description: str,
        features: list[str],
        target_column: str,
        metrics: dict[str, Any],
        model_path: Path,
        metadata_path: Path,
    ) -> str:
        """注册新模型"""
        model_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        model_info = MLModelInfo(
            id=model_id,
            name=name,
            type=model_type,
            description=description,
            created_at=now,
            last_used=now,
            session_id=session_id,
            dataset_id=dataset_id,
            features=features or [],
            target_column=target_column,
            metrics=metrics or {},
            model_path=model_path,
            metadata_path=metadata_path,
            accuracy=metrics.get("accuracy", 0.0) if metrics else 0.0,
            score=metrics.get("score", 0.0) if metrics else 0.0,
        )

        self._models[model_id] = model_info
        self._save_registry()

        logger.info(f"已注册新模型: {name} ({model_id})")
        return model_id

    def get_model(self, model_id: str) -> MLModelInfo | None:
        """获取模型信息"""
        return self._models.get(model_id)

    def list_models(self, session_id: str | None = None) -> list[MLModelInfo]:
        """列出所有模型"""
        models = list(self._models.values())
        if session_id:
            models = [m for m in models if m.session_id == session_id]
        return sorted(models, key=lambda x: x.created_at, reverse=True)

    def update_model(self, model_id: str, **kwargs: Any) -> bool:
        """更新模型信息"""
        if model_id not in self._models:
            return False

        model = self._models[model_id]
        for key, value in kwargs.items():
            if hasattr(model, key):
                setattr(model, key, value)

        model.last_used = datetime.now().isoformat()
        self._save_registry()
        return True

    def delete_model(self, model_id: str) -> bool:
        """删除模型"""
        if model_id not in self._models:
            return False

        model = self._models[model_id]

        # 删除模型文件
        try:
            if model.model_path and Path(model.model_path).exists():
                Path(model.model_path).unlink()
            if model.metadata_path and Path(model.metadata_path).exists():
                Path(model.metadata_path).unlink()

            # 删除模型目录（如果为空）
            model_dir = self.models_dir / model_id
            if model_dir.exists() and not any(model_dir.iterdir()):
                model_dir.rmdir()
        except Exception as e:
            logger.warning(f"删除模型文件失败: {e}")

        # 从注册表中删除
        del self._models[model_id]
        self._save_registry()

        logger.info(f"已删除模型: {model_id}")
        return True

    def get_model_count(self) -> int:
        """获取模型总数"""
        return len(self._models)

    def get_session_models(self, session_id: str) -> list[MLModelInfo]:
        """获取会话的所有模型"""
        return [m for m in self._models.values() if m.session_id == session_id]


# 全局模型注册表实例
model_registry = ModelRegistry()
