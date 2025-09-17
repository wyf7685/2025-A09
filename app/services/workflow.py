"""
工作流管理服务
"""

import uuid
from datetime import datetime
from pathlib import Path

import anyio

from app.const import DATA_DIR
from app.log import logger
from app.schemas.workflow import WorkflowDefinition

# 定义工作流目录
WORKFLOWS_DIR = DATA_DIR / "workflows"
# 创建目录（如果不存在）
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


class WorkflowService:
    """工作流管理服务"""

    def __init__(self) -> None:
        """初始化工作流服务"""
        self._workflows_dir = WORKFLOWS_DIR

    async def list_workflows(self) -> list[WorkflowDefinition]:
        """获取所有工作流"""
        workflows: list[WorkflowDefinition] = []

        try:
            # 列出所有工作流JSON文件
            for file_path in self._workflows_dir.glob("*.json"):
                try:
                    if workflow := await self._load_workflow_file(file_path):
                        workflows.append(workflow)
                except Exception as e:
                    logger.error(f"加载工作流文件 {file_path} 失败: {e}")
        except Exception as e:
            logger.error(f"列出工作流失败: {e}")

        return workflows

    async def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        """获取指定ID的工作流"""
        file_path = self._workflows_dir / f"{workflow_id}.json"

        if not file_path.exists():
            logger.warning(f"工作流文件不存在: {file_path}")
            return None

        try:
            return await self._load_workflow_file(file_path)
        except Exception as e:
            logger.error(f"加载工作流 {workflow_id} 失败: {e}")
            return None

    async def save_workflow(self, workflow: WorkflowDefinition) -> bool:
        """保存工作流"""
        try:
            # 如果没有ID，生成一个新ID
            if not workflow.id:
                workflow.id = str(uuid.uuid4())

            # 设置时间戳
            now = datetime.now()
            if not workflow.created_at:
                workflow.created_at = now
            workflow.updated_at = now

            # 准备文件路径
            file_path = self._workflows_dir / f"{workflow.id}.json"

            # 创建备份（如果文件已存在）
            if file_path.exists():
                # 创建备份
                backup_path = file_path.with_suffix(".json.bak")
                if backup_path.exists():
                    # 如果已经有一个备份，创建第二个备份
                    second_backup = file_path.with_suffix(".json.bak2")
                    if second_backup.exists():
                        second_backup.unlink()
                    backup_path.rename(second_backup)

                # 创建新的备份
                file_path.rename(backup_path)

            # 保存工作流
            await self._save_workflow_file(file_path, workflow)
            logger.info(f"工作流 {workflow.id} 已保存")
            return True
        except Exception as e:
            logger.error(f"保存工作流失败: {e}")
            return False

    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        file_path = self._workflows_dir / f"{workflow_id}.json"

        if not file_path.exists():
            logger.warning(f"工作流 {workflow_id} 不存在，无法删除")
            return False

        try:
            # 删除文件
            file_path.unlink()
            logger.info(f"工作流 {workflow_id} 已删除")
            return True
        except Exception as e:
            logger.error(f"删除工作流 {workflow_id} 失败: {e}")
            return False

    async def _load_workflow_file(self, file_path: Path) -> WorkflowDefinition | None:
        """加载工作流文件"""
        try:
            data = await anyio.Path(file_path).read_bytes()
            return WorkflowDefinition.model_validate_json(data)
        except Exception as e:
            logger.error(f"加载工作流文件 {file_path} 失败: {e}")
            return None

    async def _save_workflow_file(self, file_path: Path, workflow: WorkflowDefinition) -> None:
        """保存工作流到文件"""
        data = workflow.model_dump_json(exclude_none=True)
        await anyio.Path(file_path).write_text(data, encoding="utf-8")


# 创建单例实例
workflow_service = WorkflowService()
