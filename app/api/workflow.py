"""
工作流管理API
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Path, status

from app.core.agent.resume import resume_tool_call
from app.core.agent.sources import Sources
from app.log import logger
from app.schemas.workflow import ExecuteWorkflowRequest, SaveWorkflowRequest, WorkflowDefinition
from app.services.datasource import datasource_service
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

        # 从会话中提取所有工具调用
        tool_calls = []
        datasource_mappings = {}

        # 从chat_history中提取工具调用
        for chat_entry in session.chat_history:
            assistant_response = chat_entry.assistant_response

            # 处理assistant_response中的tool_calls
            for tool_call_id, tool_call in assistant_response.tool_calls.items():
                try:
                    # 获取工具调用的名称和参数，支持字典和对象两种访问方式
                    if hasattr(tool_call, "name"):
                        name = tool_call.name
                    elif isinstance(tool_call, dict) and "name" in tool_call:
                        name = tool_call["name"]
                    else:
                        logger.warning(f"工具调用没有name属性: {tool_call}")
                        continue

                    # 处理参数
                    args = None
                    if hasattr(tool_call, "args"):
                        args_value = tool_call.args
                    elif isinstance(tool_call, dict) and "args" in tool_call:
                        args_value = tool_call["args"]
                    else:
                        logger.warning(f"工具调用没有args属性: {tool_call}")
                        args_value = {}

                    # 处理字符串格式的参数
                    if isinstance(args_value, str):
                        try:
                            args = json.loads(args_value)
                        except json.JSONDecodeError:
                            args = args_value
                    else:
                        args = args_value

                    # 构建工具调用字典
                    tool_call_dict = {"id": tool_call_id, "name": name, "args": args}

                    # 添加结果信息（如果有）
                    if hasattr(tool_call, "result") and tool_call.result is not None:
                        result = tool_call.result
                    elif isinstance(tool_call, dict) and "result" in tool_call:
                        result = tool_call["result"]
                    else:
                        result = None

                    if result is not None:
                        # 尝试将复杂对象序列化为可存储的形式
                        try:
                            # 检查是否需要序列化
                            json.dumps(result)
                            tool_call_dict["result"] = result
                        except (TypeError, ValueError):
                            # 如果无法直接序列化，转换为字符串
                            tool_call_dict["result"] = str(result)

                    # 添加到工具调用列表
                    tool_calls.append(tool_call_dict)
                    logger.info(f"添加工具调用: {name}")

                    # 提取数据源ID
                    if isinstance(args, dict):
                        # 处理source_id参数
                        if "source_id" in args:
                            source_id = args["source_id"]
                            datasource_mappings[source_id] = f"数据源: {source_id}"
                            logger.info(f"提取数据源ID (source_id): {source_id}")

                        # 处理dataset_id参数
                        if "dataset_id" in args:
                            dataset_id = args["dataset_id"]
                            datasource_mappings[dataset_id] = f"数据源: {dataset_id}"
                            logger.info(f"提取数据源ID (dataset_id): {dataset_id}")

                        # 处理sources列表参数
                        elif "sources" in args and isinstance(args["sources"], list):
                            for source in args["sources"]:
                                if isinstance(source, dict) and "id" in source:
                                    source_id = source["id"]
                                    datasource_mappings[source_id] = f"数据源: {source_id}"
                                    logger.info(f"提取数据源ID (sources.id): {source_id}")
                except Exception as e:
                    logger.warning(f"处理工具调用时出错: {e}")

        # 调试信息
        logger.info(f"从会话 {request.session_id} 中提取了 {len(tool_calls)} 个工具调用")

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

        # 创建数据源集合
        sources_dict = {}

        # 加载数据源并创建双向映射
        # 既支持通过 mapped_id 访问，也支持通过 source_id 访问同一个数据源
        for source_id, mapped_id in request.datasource_mappings.items():
            try:
                if await datasource_service.source_exists(mapped_id):
                    source = await datasource_service.get_source(mapped_id)
                    # 同时保存原始ID和映射后的ID，两个ID都可以访问相同的数据源
                    sources_dict[mapped_id] = source
                    sources_dict[source_id] = source
                    logger.info(f"已加载数据源: {mapped_id} (映射自 {source_id})")
                else:
                    logger.warning(f"数据源不存在: {mapped_id}")
            except Exception as e:
                logger.warning(f"加载数据源 {mapped_id} 失败: {e}")

        # 输出已加载的所有数据源
        logger.info(f"已加载 {len(sources_dict)} 个数据源: {list(sources_dict.keys())}")

        # 创建Sources对象
        sources = Sources(sources_dict)

        # 从工作流获取工具调用并执行
        try:
            # 检查工作流中的工具调用
            logger.info(f"工作流 {request.workflow_id} 中有 {len(workflow.tool_calls)} 个工具调用")
            if len(workflow.tool_calls) == 0:
                logger.warning(f"工作流 {request.workflow_id} 不包含任何工具调用")

            # 导入所需的聊天模型
            from app.schemas.chat import (
                AssistantChatMessage,
                AssistantChatMessageToolCall,
                AssistantToolCall,
                ChatEntry,
                UserChatMessage,
            )

            # 创建用户消息
            user_message = UserChatMessage(content=f"执行工作流：{workflow.name}")

            # 创建助手响应消息
            assistant_response = AssistantChatMessage()

            # 创建聊天条目
            chat_entry = ChatEntry(user_message=user_message, assistant_response=assistant_response)

            # 直接使用工作流中保存的工具调用
            for i, tool_call in enumerate(workflow.tool_calls):
                logger.info(f"处理第 {i + 1}/{len(workflow.tool_calls)} 个工具调用: {tool_call.get('name', 'unknown')}")

                # 修改工具调用中的数据源ID映射
                args = tool_call.get("args", {})
                if isinstance(args, dict):
                    # 处理source_id字段
                    if "source_id" in args and args["source_id"] in request.datasource_mappings:
                        old_id = args["source_id"]
                        args["source_id"] = request.datasource_mappings[old_id]
                        logger.info(f"已映射数据源ID (source_id): {old_id} -> {args['source_id']}")

                    # 处理dataset_id字段
                    if "dataset_id" in args and args["dataset_id"] in request.datasource_mappings:
                        old_id = args["dataset_id"]
                        args["dataset_id"] = request.datasource_mappings[old_id]
                        logger.info(f"已映射数据源ID (dataset_id): {old_id} -> {args['dataset_id']}")

                # 创建工具调用字典
                tool_call_id = tool_call.get("id", f"tool_{id(tool_call)}")
                tool_name = tool_call.get("name", "")

                # 创建工具调用对象
                lc_tool_call = {"name": tool_name, "args": args, "id": tool_call_id}

                # 将工具调用添加到助手响应中
                assistant_response.content.append(AssistantChatMessageToolCall(id=tool_call_id))
                assistant_response.tool_calls[tool_call_id] = AssistantToolCall(
                    name=tool_name, args=json.dumps(args), status="running"
                )

                # 执行工具调用
                logger.info(f"执行工具调用: {tool_name} (参数: {args})")

                try:
                    # 检查数据集ID是否存在于sources中
                    if "dataset_id" in args and not sources.exists(args["dataset_id"]):
                        available_ids = list(sources.sources.keys())
                        error_msg = (
                            f"数据源 {args['dataset_id']} 不存在，请检查数据源映射。可用的数据源ID: {available_ids}"
                        )
                        logger.error(error_msg)
                        # 记录错误
                        assistant_response.tool_calls[tool_call_id].status = "error"
                        assistant_response.tool_calls[tool_call_id].error = error_msg
                    else:
                        # 直接传入字典作为工具调用并捕获结果
                        from langchain_core.messages import ToolMessage

                        # 创建一个监听函数来捕获工具调用结果
                        original_resume_tool_call = resume_tool_call
                        tool_result = None

                        def wrapped_resume_tool_call(tool_call, sources_dict):
                            nonlocal tool_result
                            result = original_resume_tool_call(tool_call, sources_dict)
                            tool_result = result
                            return result

                        # 临时替换函数以捕获结果
                        import app.core.agent.resume as resume_module

                        resume_module.resume_tool_call = wrapped_resume_tool_call

                        # 执行工具调用
                        try:
                            result = resume_tool_call(lc_tool_call, {"sources": sources})

                            # 更新工具调用状态为成功
                            assistant_response.tool_calls[tool_call_id].status = "success"

                            # 提取结果内容
                            if isinstance(result, ToolMessage):
                                result_content = result.content
                            else:
                                result_content = str(result)

                            assistant_response.tool_calls[tool_call_id].result = result_content
                            logger.info(f"工具调用执行成功: {tool_name}, 结果: {result_content[:100]}...")
                        finally:
                            # 恢复原始函数
                            resume_module.resume_tool_call = original_resume_tool_call
                except Exception as e:
                    # 更新工具调用状态为错误
                    assistant_response.tool_calls[tool_call_id].status = "error"
                    assistant_response.tool_calls[tool_call_id].error = str(e)

                    logger.exception(f"工具调用 {tool_name} 执行失败: {e}")

                logger.info(f"已执行工具调用: {tool_name}")

            # 将聊天条目添加到会话历史中
            session.chat_history.append(chat_entry)

            # 保存会话
            await session_service.save_session(session)
            logger.info(f"已将工作流执行结果添加到会话 {request.session_id} 的聊天历史中")
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
