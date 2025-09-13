"""
工作流管理服务
"""
import json
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
        workflows = []
        
        try:
            # 列出所有工作流JSON文件
            for file_path in self._workflows_dir.glob("*.json"):
                try:
                    workflow = await self._load_workflow_file(file_path)
                    if workflow:
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
            # 首先尝试使用utf-8-sig编码读取（可以处理带BOM的UTF-8文件）
            content = await anyio.Path(file_path).read_text(encoding="utf-8-sig")
            # 解析JSON
            data = json.loads(content)
            # 转换为WorkflowDefinition对象
            return WorkflowDefinition.model_validate(data)
        except UnicodeDecodeError:
            # 如果utf-8-sig解码失败，尝试使用其他编码
            logger.warning(f"工作流文件 {file_path} 编码解析失败，尝试其他编码...")
            try:
                # 尝试二进制读取并使用latin-1编码（可以读取任何字节）
                content = await anyio.Path(file_path).read_bytes()
                content_str = content.decode("latin-1")
                # 尝试解析JSON
                data = json.loads(content_str)
                # 转换并保存为UTF-8-sig
                workflow = WorkflowDefinition.model_validate(data)
                await self._save_workflow_file(file_path, workflow)
                logger.info(f"工作流文件 {file_path} 已转换为UTF-8编码")
                return workflow
            except Exception as e:
                logger.error(f"尝试使用其他编码解析工作流文件 {file_path} 失败: {e}")
                return None
        except Exception as e:
            logger.error(f"加载工作流文件 {file_path} 失败: {e}")
            return None
    
    async def _save_workflow_file(self, file_path: Path, workflow: WorkflowDefinition) -> None:
        """保存工作流到文件"""
        # 转换为字典
        data = workflow.model_dump(exclude_none=True)
        # 转换为JSON字符串，添加datetime序列化处理
        content = json.dumps(data, ensure_ascii=False, indent=4, default=self._json_serial)
        # 写入文件
        await anyio.Path(file_path).write_text(content, encoding="utf-8")
        
    def _json_serial(self, obj: object) -> str:
        """处理JSON序列化中的特殊对象类型"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        # 其他类型可以在这里添加处理
        raise TypeError(f"类型 {type(obj)} 不能被序列化为JSON")


# 创建单例实例
workflow_service = WorkflowService()