"""
工作流管理API
"""

import json
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import StreamingResponse

from app.log import logger
from app.schemas.chat import ChatEntry, UserChatMessage
from app.schemas.session import Session
from app.schemas.workflow import ExecuteWorkflowRequest, SaveWorkflowRequest, WorkflowDefinition
from app.services.agent import daa_service
from app.services.session import session_service
from app.services.workflow import execute_workflow_stream, extract_from_session, workflow_service
from app.utils import buffered_stream

from ._depends import CurrentSessionFromBody

router = APIRouter(prefix="/workflow", tags=["Workflow"])


@router.get("", response_model=list[WorkflowDefinition])
async def list_workflows() -> list[WorkflowDefinition]:
    """获取所有工作流"""
    try:
        return await workflow_service.list_workflows()
    except Exception as e:
        logger.exception("获取工作流列表失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取工作流列表失败: {e}") from e


@router.get("/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(workflow_id: str = Path(description="工作流ID")) -> WorkflowDefinition:
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
async def save_workflow(request: SaveWorkflowRequest, session: CurrentSessionFromBody) -> WorkflowDefinition:
    """保存工作流"""
    try:
        # 从会话中提取工作流
        workflow = await extract_from_session(session, request.name, request.description)

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


async def generate_workflow_execution_stream(
    session: Session,
    workflow: WorkflowDefinition,
    datasource_mappings: dict[str, str],
) -> AsyncIterator[str]:
    """生成工作流执行的流式响应"""
    try:
        # 构造工作流执行消息
        workflow_message = (
            f"执行工作流：{workflow.name}\n"
            f"描述：{workflow.description}\n"
            f"将按顺序执行 {len(workflow.tool_calls)} 个工具调用"
        )

        chat_entry = ChatEntry(user_message=UserChatMessage(content=workflow_message))

        # 使用 workflow_service 的流式执行
        async for event in buffered_stream(execute_workflow_stream(session, workflow, datasource_mappings), 10):
            try:
                msg = event.model_dump_json().replace("/", "\\/") + "\n"
            except Exception:
                logger.exception("转换事件为 JSON 失败")
            else:
                yield msg

            chat_entry.add_stream_event(event)

        # 记录对话历史
        chat_entry.merge_text()
        session.chat_history.append(chat_entry)

        # 生成会话标题
        async with daa_service.use_agent(session) as agent:
            session.name = await agent.create_title()
            logger.info(f"设置会话 {session.id} 名称为: {session.name}")

        await session_service.save_session(session)

        # 发送完成信号
        yield json.dumps({"type": "done", "timestamp": datetime.now().isoformat()}) + "\n"

    except Exception as e:
        logger.exception("工作流执行失败")
        yield json.dumps({"error": f"工作流执行失败: {e!r}"}) + "\n"


@router.post("/execute")
async def execute_workflow(request: ExecuteWorkflowRequest, session: CurrentSessionFromBody) -> StreamingResponse:
    """执行工作流 - 通过流式接口返回执行过程"""
    try:
        # 获取工作流
        workflow = await workflow_service.get_workflow(request.workflow_id)
        if not workflow:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {request.workflow_id} 不存在")

        # 使用流式响应执行工作流
        return StreamingResponse(
            generate_workflow_execution_stream(session, workflow, request.datasource_mappings),
            media_type="text/event-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"执行工作流失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"执行工作流失败: {e}") from e


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str = Path(description="工作流ID")) -> dict:
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
async def update_workflow(updates: dict, workflow_id: str = Path(description="工作流ID")) -> WorkflowDefinition:
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
