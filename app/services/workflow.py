"""
工作流管理服务
"""

import contextlib
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import TYPE_CHECKING, Any

import anyio
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolCall, ToolMessage

from app.const import DATA_DIR
from app.core.agent.agents.data_analyzer import get_agent_random_state
from app.core.agent.events import ToolCallEvent, ToolErrorEvent, ToolResultEvent
from app.core.agent.resume import get_resumable_tools, is_resumable_tool, resume_tool_call
from app.core.agent.sources import Sources
from app.core.agent.tools import tool_name_human_repr
from app.core.chain.llm import get_llm_async
from app.log import logger
from app.schemas.chat import (
    AssistantChatMessage,
    AssistantChatMessageToolCall,
    AssistantToolCall,
    ChatEntry,
    UserChatMessage,
)
from app.schemas.session import Session
from app.schemas.workflow import WorkflowDefinition, WorkflowToolCall
from app.services.agent import daa_service
from app.services.datasource import datasource_service
from app.services.session import session_service

if TYPE_CHECKING:
    from app.core.datasource import DataSource

# 定义工作流目录
WORKFLOWS_DIR = DATA_DIR / "workflows"
# 创建目录（如果不存在）
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


class WorkflowService:
    """工作流管理服务"""

    def __init__(self) -> None:
        """初始化工作流服务"""
        self._workflows_dir = anyio.Path(WORKFLOWS_DIR)

    async def list_workflows(self) -> list[WorkflowDefinition]:
        """获取所有工作流"""
        workflows: list[WorkflowDefinition] = []

        try:
            # 列出所有工作流JSON文件
            async for file_path in self._workflows_dir.glob("*.json"):
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

        if not await file_path.exists():
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
            if await file_path.exists():
                # 创建备份
                backup_path = file_path.with_suffix(".json.bak")
                if await backup_path.exists():
                    # 如果已经有一个备份，创建第二个备份
                    second_backup = file_path.with_suffix(".json.bak2")
                    await second_backup.unlink(missing_ok=True)
                    await backup_path.rename(second_backup)

                # 创建新的备份
                await file_path.rename(backup_path)

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

        if not await file_path.exists():
            logger.warning(f"工作流 {workflow_id} 不存在，无法删除")
            return False

        try:
            # 删除文件
            await file_path.unlink()
            logger.info(f"工作流 {workflow_id} 已删除")
            return True
        except Exception as e:
            logger.error(f"删除工作流 {workflow_id} 失败: {e}")
            return False

    async def _load_workflow_file(self, file_path: anyio.Path) -> WorkflowDefinition | None:
        """加载工作流文件"""
        try:
            data = await file_path.read_bytes()
            return WorkflowDefinition.model_validate_json(data)
        except Exception as e:
            logger.error(f"加载工作流文件 {file_path} 失败: {e}")
            return None

    async def _save_workflow_file(self, file_path: anyio.Path, workflow: WorkflowDefinition) -> None:
        """保存工作流到文件"""
        try:
            data = workflow.model_dump_json(exclude_none=True, indent=2)
            await file_path.write_text(data, encoding="utf-8")

            # 验证保存是否成功
            saved_data = await file_path.read_text(encoding="utf-8")
            saved_workflow = WorkflowDefinition.model_validate_json(saved_data)

            logger.info(
                f"工作流已保存到 {file_path.name}:\n"
                f"  - 工具调用数: {len(workflow.tool_calls)}\n"
                f"  - 文件大小: {len(data)} 字节\n"
                f"  - 验证: 保存后读取到 {len(saved_workflow.tool_calls)} 个工具调用"
            )

            if len(saved_workflow.tool_calls) != len(workflow.tool_calls):
                logger.error(
                    f"⚠️ 工作流保存验证失败! "
                    f"原始: {len(workflow.tool_calls)} vs 保存后: {len(saved_workflow.tool_calls)}"
                )
        except Exception as e:
            logger.error(f"保存工作流文件失败: {e}")
            raise

    @staticmethod
    async def extract_from_session(session: Session, name: str, description: str) -> WorkflowDefinition:
        # 从会话中提取所有工具调用
        tool_calls: list[WorkflowToolCall] = []

        # 记录可恢复工具列表
        resumable_tools = get_resumable_tools()
        logger.info(f"当前已注册 {len(resumable_tools)} 个可恢复工具: {resumable_tools[:10]}...")

        # 统计信息
        total_tool_calls = 0
        skipped_non_resumable = 0
        failed_to_parse = 0

        # 从chat_history中提取工具调用
        for entry_idx, chat_entry in enumerate(session.chat_history):
            assistant_response = chat_entry.assistant_response

            # 处理assistant_response中的tool_calls
            for tool_call_id, tool_call in assistant_response.tool_calls.items():
                total_tool_calls += 1
                try:
                    # 检查工具是否可恢复
                    if not is_resumable_tool(tool_call.name):
                        logger.warning(
                            f"跳过不可恢复的工具调用 [{entry_idx + 1}]: {tool_call.name} (ID: {tool_call_id})"
                        )
                        skipped_non_resumable += 1
                        continue

                    # 处理参数
                    args = json.loads(tool_call.args)

                    # 构建工具调用字典
                    tool_call_data = WorkflowToolCall(id=tool_call_id, name=tool_call.name, args=args)

                    # 添加结果信息（如果有）
                    if (result := tool_call.result) is not None:
                        # 尝试将复杂对象序列化为可存储的形式
                        try:
                            # 检查是否需要序列化
                            json.dumps(result)
                            tool_call_data.result = result
                        except (TypeError, ValueError):
                            # 如果无法直接序列化，转换为字符串
                            tool_call_data.result = str(result)

                    # 添加到工具调用列表
                    tool_calls.append(tool_call_data)
                    logger.info(f"✓ 添加工具调用 [{entry_idx + 1}]: {tool_call.name} (ID: {tool_call_id})")

                except Exception as e:
                    logger.warning(f"✗ 处理工具调用 [{entry_idx + 1}] 时出错 (ID: {tool_call_id}): {e}")
                    failed_to_parse += 1

        # 详细的调试信息
        logger.info(
            f"从会话 {session.id} 提取工具调用统计:\n"
            f"  - 总工具调用数: {total_tool_calls}\n"
            f"  - 成功提取: {len(tool_calls)}\n"
            f"  - 跳过(不可恢复): {skipped_non_resumable}\n"
            f"  - 解析失败: {failed_to_parse}"
        )

        datasets: dict[str, str] = {}
        for ds_id in session.dataset_ids:
            source = await datasource_service.get_source(ds_id)
            datasets[ds_id] = source.metadata.name or ds_id

        # 创建工作流
        return WorkflowDefinition(
            name=name,
            description=description,
            tool_calls=tool_calls,
            initial_datasets=datasets,
            source_rs=get_agent_random_state(session.id),
        )

    @staticmethod
    @contextlib.asynccontextmanager
    async def _fetch_sources_for_workflow(
        session: Session,
        workflow: WorkflowDefinition,
        datasource_mappings: dict[str, str],  # original dataset ID -> mapped dataset ID
    ) -> AsyncGenerator[tuple[list[AnyMessage], Sources]]:
        async with daa_service.use_agent(session) as agent:
            original_sources = agent.ctx.sources
            sources_dict: dict[str, DataSource] = {}
            for ds_id in workflow.initial_datasets:
                if ds_id not in datasource_mappings:
                    raise ValueError(f"工作流初始数据源 {ds_id} 未设置映射")
                mapped = datasource_mappings[ds_id]
                if mapped not in original_sources.sources:
                    raise ValueError(f"当前会话中不存在数据源 {mapped}, 无法映射工作流数据源 {ds_id}")
                sources_dict[ds_id] = original_sources.get(mapped).copy()

            messages: list[AnyMessage] = []
            sources = Sources(sources_dict, random_state=workflow.source_rs)

            yield messages, sources

            agent_state = await agent.get_state()
            agent_state.values.setdefault("messages", []).extend(messages)
            agent.ctx.graph.update_state(agent.ctx.runnable_config, agent_state.values)

            reversed_mapping = {v: k for k, v in datasource_mappings.items()}
            for source_id, source in sources.items():
                original_id = reversed_mapping.get(source_id)
                agent.ctx.sources.sources[original_id or source_id] = source

    @classmethod
    async def execute_workflow(
        cls,
        session: Session,
        workflow: WorkflowDefinition,
        datasource_mappings: dict[str, str],  # original dataset ID -> mapped dataset ID
    ) -> None:
        # 检查工作流中的工具调用
        logger.info(f"工作流 {workflow.id} 中有 {len(workflow.tool_calls)} 个工具调用")
        if len(workflow.tool_calls) == 0:
            logger.warning(f"工作流 {workflow.id} 不包含任何工具调用")
            return

        # 创建聊天条目
        chat_entry = ChatEntry(
            user_message=UserChatMessage(content=f"执行工作流：{workflow.name}"),
            assistant_response=(assistant_response := AssistantChatMessage()),
        )

        def entry_append_tool_call() -> None:
            assistant_response.content.append(AssistantChatMessageToolCall(id=tool_call_id))
            assistant_response.tool_calls[tool_call_id] = AssistantToolCall(
                name=tool_name,
                args=json.dumps(tool_call.args) if isinstance(tool_call.args, dict) else tool_call.args,
                status="running",
            )
            tool_call_dict: ToolCall = {
                "name": tool_name,
                "args": tool_call.args,
                "id": tool_call_id,
                "type": "tool_call",
            }
            if not messages or not isinstance(messages[-1], AIMessage):
                messages.append(AIMessage(content="", tool_calls=[tool_call_dict]))
            else:
                messages[-1].tool_calls.append(tool_call_dict)

        def tool_call_success(result: str, artifact: dict | None = None) -> None:
            entry_append_tool_call()

            result_with_artifact = result
            if artifact and isinstance(artifact, dict) and artifact.get("type") == "image":
                image_base64 = artifact.get("base64_data", "")
                caption = artifact.get("caption", "分析结果图表")
                result_with_artifact = f"{result}\n\n![{caption}](data:image/png;base64,{image_base64})"
                logger.info("工具调用返回了图像结果")

            assistant_response.tool_calls[tool_call_id].status = "success"
            assistant_response.tool_calls[tool_call_id].result = result_with_artifact
            messages.append(ToolMessage(tool_call_id=tool_call_id, content=result, artifact=artifact, status="success"))

        def tool_call_error(error_msg: str) -> None:
            entry_append_tool_call()
            assistant_response.tool_calls[tool_call_id].status = "error"
            assistant_response.tool_calls[tool_call_id].error = error_msg
            messages.append(ToolMessage(tool_call_id=tool_call_id, content=error_msg, status="error"))

        async with cls._fetch_sources_for_workflow(session, workflow, datasource_mappings) as (messages, sources):
            messages.append(HumanMessage(content=f"执行工作流：{workflow.name}"))

            # 直接使用工作流中保存的工具调用
            for idx, tool_call in enumerate(workflow.tool_calls, 1):
                logger.info(f"处理第 {idx}/{len(workflow.tool_calls)} 个工具调用: {tool_call.name}")
                tool_call_id = tool_call.id or f"tool_{id(tool_call)}"
                tool_name = tool_call.name or ""
                tool_args = tool_call.args

                # 执行工具调用
                logger.info(f"执行工具调用: {tool_name} (参数: {tool_call.args})")

                try:
                    # 执行工具调用
                    try:
                        result = resume_tool_call(
                            tool_call={"name": tool_name, "args": tool_args, "id": tool_call_id},
                            extra={"sources": sources},
                        )
                    except Exception as tool_error:
                        # 更新工具调用状态为错误
                        tool_call_error(str(tool_error))
                        logger.exception(f"工具 {tool_name} 执行过程中发生错误: {tool_error}")
                        continue

                    # 处理工具返回的结果
                    if isinstance(result, tuple) and len(result) == 2:
                        # 处理可能的图像结果（如analyze_data工具）
                        text_result, artifact = result
                        # 提取文本内容
                        result_content = str(
                            text_result.content if isinstance(text_result, ToolMessage) else text_result
                        )
                        tool_call_success(result_content, artifact)
                    else:
                        # 标准的文本结果处理
                        result_content = str(result.content if isinstance(result, ToolMessage) else result)
                        tool_call_success(result_content)

                    # 截取结果的前100个字符显示在日志中
                    result_str = str(result_content)
                    truncated_result = result_str[:100] + "..." if len(result_str) > 100 else result_str
                    logger.info(f"工具调用执行成功: {tool_name}, 结果: {truncated_result}")

                except Exception as e:
                    # 更新工具调用状态为错误
                    tool_call_error(str(e))
                    logger.exception(f"工具调用 {tool_name} 执行失败: {e}")

                logger.info(f"已执行工具调用: {tool_name}")

        session.chat_history.append(chat_entry)
        await session_service.save_session(session)

    @classmethod
    async def execute_workflow_stream(
        cls,
        session: Session,
        workflow: WorkflowDefinition,
        datasource_mappings: dict[str, str],
    ) -> AsyncGenerator[Any]:
        """流式执行工作流，生成事件供前端显示"""

        # 检查工作流中的工具调用
        logger.info(f"工作流 {workflow.id} 中有 {len(workflow.tool_calls)} 个工具调用")
        if len(workflow.tool_calls) == 0:
            logger.warning(f"工作流 {workflow.id} 不包含任何工具调用")
            return

        # 创建聊天条目
        chat_entry = ChatEntry(
            user_message=UserChatMessage(content=f"执行工作流：{workflow.name}"),
            assistant_response=(assistant_response := AssistantChatMessage()),
        )

        def entry_append_tool_call() -> None:
            assistant_response.content.append(AssistantChatMessageToolCall(id=tool_call_id))
            assistant_response.tool_calls[tool_call_id] = AssistantToolCall(
                name=tool_name,
                args=json.dumps(tool_call.args) if isinstance(tool_call.args, dict) else tool_call.args,
                status="running",
            )
            tool_call_dict: ToolCall = {
                "name": tool_name,
                "args": tool_call.args,
                "id": tool_call_id,
                "type": "tool_call",
            }
            if not messages or not isinstance(messages[-1], AIMessage):
                messages.append(AIMessage(content="", tool_calls=[tool_call_dict]))
            else:
                messages[-1].tool_calls.append(tool_call_dict)

        def tool_call_success(result: str, artifact: dict | None = None) -> None:
            entry_append_tool_call()

            result_with_artifact = result
            if artifact and isinstance(artifact, dict) and artifact.get("type") == "image":
                image_base64 = artifact.get("base64_data", "")
                caption = artifact.get("caption", "分析结果图表")
                result_with_artifact = f"{result}\n\n![{caption}](data:image/png;base64,{image_base64})"
                logger.info("工具调用返回了图像结果")

            assistant_response.tool_calls[tool_call_id].status = "success"
            assistant_response.tool_calls[tool_call_id].result = result_with_artifact
            messages.append(ToolMessage(tool_call_id=tool_call_id, content=result, artifact=artifact, status="success"))

        def tool_call_error(error_msg: str) -> None:
            entry_append_tool_call()
            assistant_response.tool_calls[tool_call_id].status = "error"
            assistant_response.tool_calls[tool_call_id].error = error_msg
            messages.append(ToolMessage(tool_call_id=tool_call_id, content=error_msg, status="error"))

        async with cls._fetch_sources_for_workflow(session, workflow, datasource_mappings) as (messages, sources):
            messages.append(HumanMessage(content=f"执行工作流：{workflow.name}"))
            codegen_llm = await get_llm_async(
                session.agent_model_config.code_generation or session.agent_model_config.default
            )

            # 逐个执行工具调用并生成事件
            for idx, tool_call in enumerate(workflow.tool_calls, 1):
                tool_call_id = tool_call.id or f"tool_{id(tool_call)}"
                tool_name = tool_call.name or ""
                tool_args = tool_call.args.copy() if isinstance(tool_call.args, dict) else tool_call.args

                logger.info(f"处理第 {idx}/{len(workflow.tool_calls)} 个工具调用: {tool_name}")
                logger.info(f"工具参数(原始): {tool_args}")
                logger.info(f"当前Sources中的数据源: {list(sources.sources.keys())}")

                # 发送工具调用事件
                yield ToolCallEvent(
                    id=tool_call_id, name=tool_name, human_repr=tool_name_human_repr(tool_name), args=tool_args
                )

                try:
                    # 执行工具调用
                    result = resume_tool_call(
                        tool_call={"name": tool_name, "args": tool_args, "id": tool_call_id},
                        extra={"sources": sources, "codegen_llm": codegen_llm},
                    )

                    # 处理工具返回的结果
                    if isinstance(result, tuple) and len(result) == 2:
                        # 处理可能的图像结果
                        text_result, artifact = result
                        result_content = str(
                            text_result.content if isinstance(text_result, ToolMessage) else text_result
                        )
                        yield ToolResultEvent(id=tool_call_id, result=result_content, artifact=artifact)
                        tool_call_success(result_content, artifact)
                    else:
                        # 标准的文本结果处理
                        result_content = str(result.content if isinstance(result, ToolMessage) else result)
                        yield ToolResultEvent(id=tool_call_id, result=result_content)
                        tool_call_success(result_content)

                    logger.info(f"工具调用执行成功: {tool_name}")

                except Exception as e:
                    # 发送错误事件
                    error_msg = str(e)
                    yield ToolErrorEvent(id=tool_call_id, error=error_msg)
                    tool_call_error(error_msg)
                    logger.exception(f"工具调用 {tool_name} 执行失败: {e}")

        session.chat_history.append(chat_entry)
        await session_service.save_session(session)


# 创建单例实例
workflow_service = WorkflowService()
