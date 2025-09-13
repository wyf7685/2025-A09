"""
工作流存储服务
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio
from pydantic.json import pydantic_encoder

from app.log import logger
from app.schemas.workflow import WorkflowDefinition
from app.const import DATA_DIR

class WorkflowService:
    """工作流服务"""
    
    def __init__(self, base_dir: Path):
        """初始化
        
        Args:
            base_dir: 基础数据目录
        """
        self.workflows_dir = base_dir / "workflows"
        # 确保目录存在
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    async def list_workflows(self) -> list[WorkflowDefinition]:
        """列出所有工作流"""
        workflows = []
        
        try:
            for file_path in self.workflows_dir.glob("*.json"):
                try:
                    async with await anyio.open_file(file_path, encoding="utf-8") as f:
                        workflow_data = json.loads(await f.read())
                        workflow = WorkflowDefinition(**workflow_data)
                        workflows.append(workflow)
                except Exception as e:
                    logger.error(f"加载工作流文件 {file_path} 失败: {e}")
        except Exception as e:
            logger.error(f"列出工作流失败: {e}")
        
        # 按更新时间排序，最新的在前面
        workflows.sort(key=lambda w: w.updated_at, reverse=True)
        return workflows
    
    async def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        """获取单个工作流"""
        file_path = self.workflows_dir / f"{workflow_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            async with await anyio.open_file(file_path, encoding="utf-8") as f:
                workflow_data = json.loads(await f.read())
                return WorkflowDefinition(**workflow_data)
        except Exception as e:
            logger.error(f"读取工作流 {workflow_id} 失败: {e}")
            return None
    
    async def save_workflow(self, workflow: WorkflowDefinition) -> bool:
        """保存工作流"""
        try:
            # 更新时间戳
            workflow.updated_at = datetime.now()
            
            # 保存到文件
            file_path = self.workflows_dir / f"{workflow.id}.json"
            content = json.dumps(workflow.model_dump(), default=pydantic_encoder, ensure_ascii=False, indent=2)
            
            async with await anyio.open_file(file_path, "w", encoding="utf-8") as f:
                await f.write(content)
                
            return True
        except Exception as e:
            logger.error(f"保存工作流 {workflow.id} 失败: {e}")
            return False
    
    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        file_path = self.workflows_dir / f"{workflow_id}.json"
        
        if not file_path.exists():
            return False
        
        try:
            file_path.unlink()
            return True
        except Exception as e:
            logger.error(f"删除工作流 {workflow_id} 失败: {e}")
            return False


# 全局服务实例
workflow_service = WorkflowService(DATA_DIR)
