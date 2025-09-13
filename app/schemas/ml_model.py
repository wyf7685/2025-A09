from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, computed_field

from app.schemas.session import SessionID


class MLModelInfoOut(BaseModel):
    """模型信息"""

    id: str
    name: str
    type: str
    description: str = ""
    created_at: str
    last_used: str = ""
    session_id: SessionID = ""
    session_name: str = ""
    dataset_id: str = ""

    # 模型性能指标
    accuracy: float = 0.0
    score: float = 0.0
    metrics: dict[str, Any] = {}

    # 模型特征信息
    features: list[str] = []
    target_column: str = ""

    @computed_field
    @property
    def feature_count(self) -> int:
        """返回特征数量"""
        return len(self.features)

    # 状态信息
    status: Literal["created", "training", "trained", "failed"] = "trained"
    version: str = "v1.0.0"


class MLModelInfo(MLModelInfoOut):
    """模型信息"""

    # 文件路径
    model_path: Path
    metadata_path: Path
