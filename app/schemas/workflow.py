"""
工作流模型定义
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowToolCall(BaseModel):
    id: str
    name: str
    args: dict[str, Any]
    result: Any | None = None


class WorkflowDefinition(BaseModel):
    """工作流定义"""

    id: str = Field(default_factory=lambda: f"wf-{uuid.uuid4().hex}")
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tool_calls: list[WorkflowToolCall] = Field(default_factory=list)
    # datasource id -> description
    initial_datasets: dict[str, str] = Field(default_factory=dict)
    source_rs: int


class SaveWorkflowRequest(BaseModel):
    """保存工作流请求"""

    name: str
    description: str = ""
    session_id: str
    messages: list[dict] = Field(default_factory=list)


class ExecuteWorkflowRequest(BaseModel):
    """执行工作流请求"""

    workflow_id: str
    session_id: str
    datasource_mappings: dict[str, str] = Field(default_factory=dict)
