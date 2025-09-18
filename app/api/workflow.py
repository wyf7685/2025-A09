"""
工作流管理API
"""

from fastapi import APIRouter, HTTPException, Path, status

from app.log import logger
from app.schemas.workflow import ExecuteWorkflowRequest, SaveWorkflowRequest, WorkflowDefinition
from app.services.session import session_service
from app.services.workflow import workflow_service

router = APIRouter(prefix="/workflow")


@router.get("", response_model=list[WorkflowDefinition])
async def list_workflows() -> list[WorkflowDefinition]:
    """获取所有工作流"""
    try:
        return await workflow_service.list_workflows()
    except Exception as e:
        logger.exception("获取工作流列表失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取工作流列表失败: {e}") from e


@router.get("/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(workflow_id: str = Path(..., description="工作流ID")) -> WorkflowDefinition:
    """获取单个工作流"""
    try:
        workflow = await workflow_service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {workflow_id} 不存在")
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取工作流 {workflow_id} 失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取工作流失败: {e}") from e


@router.post("", response_model=WorkflowDefinition)
async def save_workflow(request: SaveWorkflowRequest) -> WorkflowDefinition:
    """保存工作流"""
    try:
        # 获取会话
        session = await session_service.get(request.session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

        # 从会话中提取工作流
        workflow = await workflow_service.extract_from_session(session, request.name, request.description)

        # 保存工作流
        success = await workflow_service.save_workflow(workflow)
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存工作流失败")

        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("保存工作流失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"保存工作流失败: {e}") from e


@router.post("/execute", response_model=dict)
async def execute_workflow(request: ExecuteWorkflowRequest) -> dict:
    """执行工作流"""
    try:
        # 获取工作流
        workflow = await workflow_service.get_workflow(request.workflow_id)
        if not workflow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {request.workflow_id} 不存在")

        # 获取会话
        session = await session_service.get(request.session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

        # 从工作流获取工具调用并执行
        try:
            await workflow_service.execute_workflow(session, workflow, request.datasource_mappings)
        except Exception as e:
            logger.exception(f"执行工具调用失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"执行工作流工具调用失败: {e}"
            ) from e

        return {
            "success": True,
            "session_id": request.session_id,
            "message": f"已成功执行工作流 {workflow.name}，共执行了 {len(workflow.tool_calls)} 个工具调用",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"执行工作流失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"执行工作流失败: {e}") from e


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str = Path(..., description="工作流ID")) -> dict:
    """删除工作流"""
    try:
        success = await workflow_service.delete_workflow(workflow_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {workflow_id} 不存在")
        return {"success": True, "message": f"已删除工作流 {workflow_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"删除工作流 {workflow_id} 失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除工作流失败: {e}") from e


@router.put("/{workflow_id}", response_model=WorkflowDefinition)
async def update_workflow(updates: dict, workflow_id: str = Path(..., description="工作流ID")) -> WorkflowDefinition:
    """更新工作流"""
    try:
        if not updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="更新数据不能为空")

        workflow = await workflow_service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {workflow_id} 不存在")

        # 更新工作流属性
        for key, value in updates.items():
            if key != "id" and hasattr(workflow, key):  # 不允许更改ID
                setattr(workflow, key, value)

        # 保存更新后的工作流
        success = await workflow_service.save_workflow(workflow)
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新工作流失败")

        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"更新工作流 {workflow_id} 失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新工作流失败: {e}") from e
