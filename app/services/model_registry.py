"""
模型注册表 - 统一管理所有训练好的模型
"""

import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio
import anyio.to_thread
from pydantic import TypeAdapter

from app.const import DATA_DIR, MODEL_DIR, TEMP_DIR
from app.core.lifespan import lifespan
from app.log import logger
from app.schemas.ml_model import MLModelInfo
from app.schemas.session import SessionID
from app.services.datasource import temp_file_service

_models_ta = TypeAdapter(dict[str, MLModelInfo])


class ModelRegistry:
    """模型注册表"""

    def __init__(self) -> None:
        self.models_dir = anyio.Path(MODEL_DIR)
        self.registry_file = anyio.Path(DATA_DIR / "model_registry.json")
        self._models: dict[str, MLModelInfo] = {}

        lifespan.on_startup(self._load_registry)
        lifespan.on_shutdown(self._save_registry)

    async def _load_registry(self) -> None:
        """加载模型注册表"""
        if await self.registry_file.exists():
            try:
                data = _models_ta.validate_json(await self.registry_file.read_bytes())
                self._models.update(data)
                logger.info(f"已加载模型注册表: {len(self._models)} 个模型")
            except Exception as e:
                logger.warning(f"加载模型注册表失败: {e}")
                self._models = {}

    async def _save_registry(self) -> None:
        """保存模型注册表"""
        try:
            await self.registry_file.write_bytes(_models_ta.dump_json(self._models))
            logger.debug("模型注册表已保存")
        except Exception as e:
            logger.error(f"保存模型注册表失败: {e}")

    def _save_registry_sync(self) -> None:
        """保存模型注册表"""
        try:
            Path(self.registry_file).write_bytes(_models_ta.dump_json(self._models))
            logger.debug("模型注册表已保存")
        except Exception as e:
            logger.error(f"保存模型注册表失败: {e}")

    def register_model(
        self,
        name: str,
        model_type: str,
        session_name: str,
        dataset_id: str,
        dataset_name: str,
        dataset_description: str,
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
            session_id="",  # 移除 session_id
            session_name=session_name,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            dataset_description=dataset_description,
            features=features or [],
            target_column=target_column,
            metrics=metrics or {},
            model_path=model_path,
            metadata_path=metadata_path,
            accuracy=metrics.get("accuracy", 0.0) if metrics else 0.0,
        )

        self._models[model_id] = model_info
        self._save_registry_sync()

        logger.info(f"已注册新模型: {name} ({model_id})")
        return model_id

    def get_model(self, model_id: str) -> MLModelInfo | None:
        """获取模型信息"""
        return self._models.get(model_id)

    def list_models(self, session_id: SessionID | None = None) -> list[MLModelInfo]:
        """列出所有模型"""
        models = list(self._models.values())
        if session_id:
            models = [m for m in models if m.session_id == session_id]
        return sorted(models, key=lambda x: x.created_at, reverse=True)

    async def delete_model(self, model_id: str) -> bool:
        """删除模型"""
        if model_id not in self._models:
            return False

        model = self._models[model_id]

        # 删除模型文件
        try:
            model.model_path.unlink(missing_ok=True)
            model.metadata_path.unlink(missing_ok=True)

            # 删除模型目录（如果为空）
            model_dir = self.models_dir / model_id
            if await model_dir.exists() and not anext(model_dir.iterdir(), None):
                await model_dir.rmdir()
        except Exception as e:
            logger.warning(f"删除模型文件失败: {e}")

        # 从注册表中删除
        del self._models[model_id]
        await self._save_registry()

        logger.info(f"已删除模型: {model_id}")
        return True

    def get_model_count(self) -> int:
        """获取模型总数"""
        return len(self._models)

    def get_session_models(self, session_id: SessionID) -> list[MLModelInfo]:
        """获取会话的所有模型"""
        return [m for m in self._models.values() if m.session_id == session_id]

    def _pack_model_archive(self, model_id: str) -> Path:
        """打包模型为二进制数据"""
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        temp_dir = TEMP_DIR / f"pack_model_{uuid.uuid4()}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            # 复制模型文件到临时目录
            shutil.copyfile(model.model_path, temp_dir / model.model_path.name)
            shutil.copyfile(model.metadata_path, temp_dir / model.metadata_path.name)

            # 打包为 zip 文件
            archive = temp_dir.with_suffix(".zip")
            shutil.make_archive(archive.stem, "zip", temp_dir)

            logger.info(f"模型 {model_id} 已打包为 {archive}")
            return archive

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def pack_model(self, model_id: str) -> Path:
        archive = await anyio.to_thread.run_sync(self._pack_model_archive, model_id)
        file_id = await temp_file_service.register(archive, ttl=3600)
        temp_path = temp_file_service.get(file_id)
        assert temp_path is not None
        return temp_path


# 全局模型注册表实例
model_registry = ModelRegistry()
