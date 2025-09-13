"""
工作流管理API
"""
from fastapi import APIRouter, HTTPException, Path, status
from langchain_core.messages import ToolCall

from app.core.agent.resume import resume_tool_call
from app.core.agent.sources import Sources
from app.log import logger
from app.schemas.workflow import WorkflowDefinition, SaveWorkflowRequest, ExecuteWorkflowRequest
from app.services.session import session_service
from app.services.workflow import workflow_service
from app.services.datasource import datasource_service

router = APIRouter(prefix="/workflow")


@router.get("", response_model=list[WorkflowDefinition])
async def list_workflows() -> list[WorkflowDefinition]:
    """获取所有工作流"""
    try:
        return await workflow_service.list_workflows()
    except Exception as e:
        logger.exception("获取工作流列表失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取工作流列表失败: {e}"
        ) from e


@router.get("/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(workflow_id: str = Path(..., description="工作流ID")) -> WorkflowDefinition:
    """获取单个工作流"""
    try:
        workflow = await workflow_service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {workflow_id} 不存在"
            )
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取工作流 {workflow_id} 失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取工作流失败: {e}"
        ) from e


@router.post("", response_model=WorkflowDefinition)
async def save_workflow(request: SaveWorkflowRequest) -> WorkflowDefinition:
    """保存工作流"""
    try:
        # 获取会话
        session = await session_service.get(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        
        # 从会话中提取所有工具调用
        # 会话可能是字典或Session对象，根据类型提取消息
        if session is None:
            messages = []
        elif isinstance(session, dict):
            messages = session.get("messages", [])
        else:
            messages = getattr(session, "messages", [])
        tool_calls = []
        datasource_mappings = {}
        
        # 收集所有工具调用
        for message in messages:
            if message.get("role") == "assistant" and message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    if isinstance(tool_call, dict) and "name" in tool_call and "args" in tool_call:
                        tool_calls.append(tool_call)
                        
                        # 从参数中提取数据源ID进行映射
                        args = tool_call.get("args", {})
                        if isinstance(args, dict):
                            if "source_id" in args:
                                source_id = args["source_id"]
                                datasource_mappings[source_id] = f"数据源: {source_id}"
                            elif "sources" in args and isinstance(args["sources"], list):
                                for source in args["sources"]:
                                    if isinstance(source, dict) and "id" in source:
                                        source_id = source["id"]
                                        datasource_mappings[source_id] = f"数据源: {source_id}"
        
        # 创建工作流
        workflow = WorkflowDefinition(
            name=request.name,
            description=request.description,
            tool_calls=tool_calls,
            datasource_mappings=datasource_mappings,
        )
        
        # 保存工作流
        success = await workflow_service.save_workflow(workflow)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存工作流失败"
            )
        
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("保存工作流失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"保存工作流失败: {e}"
        ) from e


@router.post("/execute", response_model=dict)
async def execute_workflow(request: ExecuteWorkflowRequest) -> dict:
    """执行工作流"""
    try:
        # 获取工作流
        workflow = await workflow_service.get_workflow(request.workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {request.workflow_id} 不存在"
            )
        
        # 获取会话
        session = await session_service.get(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
            )
        
        # 创建数据源集合
        sources_dict = {}
        
        # 加载数据源
        for source_id, mapped_id in request.datasource_mappings.items():
            try:
                if await datasource_service.source_exists(mapped_id):
                    source = await datasource_service.get_source(mapped_id)
                    sources_dict[mapped_id] = source
                    logger.info(f"已加载数据源: {mapped_id} (映射自 {source_id})")
                else:
                    logger.warning(f"数据源不存在: {mapped_id}")
            except Exception as e:
                logger.warning(f"加载数据源 {mapped_id} 失败: {e}")
                
        # 创建Sources对象
        sources = Sources(sources_dict)
        
        # 从工作流获取工具调用并执行
        try:
            # 直接使用工作流中保存的工具调用
            for tool_call in workflow.tool_calls:
                # 修改工具调用中的数据源ID映射
                args = tool_call.get("args", {})
                if isinstance(args, dict) and "source_id" in args and args["source_id"] in request.datasource_mappings:
                    args["source_id"] = request.datasource_mappings[args["source_id"]]
                
                # 从字典转换为ToolCall对象
                from langchain_core.messages import ToolCall as LCToolCall
                lc_tool_call = LCToolCall(
                    name=tool_call.get("name", ""),
                    args=args,
                    id=tool_call.get("id", f"tool_{id(tool_call)}")
                )
                
                # 执行工具调用
                resume_tool_call(lc_tool_call, {"sources": sources})
                
                logger.info(f"已执行工具调用: {tool_call.get('name', 'unknown')}")
                
        except Exception as e:
            logger.exception(f"执行工具调用失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"执行工作流工具调用失败: {e}"
            ) from e
        
        return {
            "success": True,
            "session_id": request.session_id,
            "message": f"已成功执行工作流 {workflow.name}，共执行了 {len(workflow.tool_calls)} 个工具调用"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"执行工作流失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"执行工作流失败: {e}"
        ) from e


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str = Path(..., description="工作流ID")) -> dict:
    """删除工作流"""
    try:
        success = await workflow_service.delete_workflow(workflow_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {workflow_id} 不存在"
            )
        return {"success": True, "message": f"已删除工作流 {workflow_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"删除工作流 {workflow_id} 失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除工作流失败: {e}"
        ) from e


@router.put("/{workflow_id}", response_model=WorkflowDefinition)
async def update_workflow(
    updates: dict,
    workflow_id: str = Path(..., description="工作流ID")
) -> WorkflowDefinition:
    """更新工作流"""
    try:
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="更新数据不能为空"
            )
            
        workflow = await workflow_service.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"工作流 {workflow_id} 不存在"
            )
        
        # 更新工作流属性
        for key, value in updates.items():
            if key != "id" and hasattr(workflow, key):  # 不允许更改ID
                setattr(workflow, key, value)
        
        # 保存更新后的工作流
        success = await workflow_service.save_workflow(workflow)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新工作流失败"
            )
        
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"更新工作流 {workflow_id} 失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新工作流失败: {e}"
        ) from e
