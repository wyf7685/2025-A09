"""
工作流管理API
"""

import json

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

        # 查找会话中的所有Dremio数据源
        dremio_sources = []
        for dataset_id in session.dataset_ids:
            if dataset_id.startswith("dremio_"):
                dremio_sources.append(dataset_id)

        # 首先尝试同步Dremio数据源 - 解决可能的数据源不存在问题
        try:
            await datasource_service.sync_from_dremio()
            logger.info("已同步Dremio数据源")
        except Exception as e:
            logger.warning(f"同步Dremio数据源失败: {e}")

        # 尝试手动重新加载外部数据源文件夹
        try:
            # 这里我们避免直接调用内部方法，而是通过公共API来刷新数据源
            # 先获取当前所有数据源信息作为参考
            all_sources = list(datasource_service.sources.keys())
            logger.info(f"当前系统中有 {len(all_sources)} 个数据源")

            # 主动尝试加载每个会话数据源
            for dataset_id in session.dataset_ids:
                if dataset_id not in datasource_service.sources:
                    try:
                        # 尝试直接加载 - 这会访问文件系统
                        await datasource_service.source_exists(dataset_id)
                        logger.info(f"已检查数据源: {dataset_id}")
                    except Exception as load_err:
                        logger.warning(f"检查数据源失败: {dataset_id}, 错误: {load_err}")
        except Exception as e:
            logger.warning(f"加载数据源失败: {e}")

        # 确保会话中的所有数据源都被加载
        for dataset_id in session.dataset_ids:
            try:
                if await datasource_service.source_exists(dataset_id):
                    source = await datasource_service.get_source(dataset_id)

                    # 添加主ID映射
                    sources_dict[dataset_id] = source

                    # 添加各种可能的ID格式映射
                    if dataset_id.startswith("dremio_"):
                        # 标准格式: dremio_<uuid>
                        base_id = dataset_id[7:]  # 移除 "dremio_" 前缀

                        # 格式1: dremio_external_<uuid>
                        external_id = f"dremio_external_{base_id}"
                        sources_dict[external_id] = source

                        # 格式2: dremio_external_<uuid>_csv
                        csv_id = f"{external_id}_csv"
                        sources_dict[csv_id] = source

                        logger.info(f"已添加Dremio数据源额外映射: {dataset_id} -> {external_id}, {csv_id}")

                    logger.info(f"已从会话加载数据源: {dataset_id}")
                else:
                    logger.warning(f"会话中的数据源不存在: {dataset_id}")
            except Exception as e:
                logger.warning(f"从会话加载数据源 {dataset_id} 失败: {e}")

        # 添加特殊映射以处理可能的格式变体
        for source_id in list(sources_dict.keys()):  # 使用list避免在迭代中修改字典
            source = sources_dict[source_id]

            # 处理可能的格式变体
            if source_id.endswith("_csv"):
                base_id = source_id[:-4]  # 移除 "_csv" 后缀
                if base_id not in sources_dict:
                    sources_dict[base_id] = source
                    logger.info(f"已添加无CSV后缀映射: {source_id} -> {base_id}")

            # 从dremio_external_格式转换回dremio_格式
            if source_id.startswith("dremio_external_"):
                base_id = source_id[15:]  # 移除 "dremio_external_" 前缀
                dremio_id = f"dremio_{base_id}"
                if dremio_id not in sources_dict and dremio_id in dremio_sources:
                    sources_dict[dremio_id] = source
                    logger.info(f"已添加Dremio反向映射: {source_id} -> {dremio_id}")

        # 然后，处理工作流请求中指定的数据源映射
        for source_id, mapped_id in request.datasource_mappings.items():
            try:
                if await datasource_service.source_exists(mapped_id):
                    source = await datasource_service.get_source(mapped_id)

                    # 同时保存原始ID和映射后的ID，两个ID都可以访问相同的数据源
                    sources_dict[mapped_id] = source
                    sources_dict[source_id] = source

                    # 处理常见的ID格式变体
                    format_variants = []

                    # 如果是Dremio数据源，添加各种变体
                    if mapped_id.startswith("dremio_"):
                        base_id = mapped_id[7:]  # 移除 "dremio_" 前缀
                        format_variants.extend([f"dremio_external_{base_id}", f"dremio_external_{base_id}_csv"])

                    # 添加所有变体到源字典
                    for variant in format_variants:
                        sources_dict[variant] = source
                        logger.info(f"已添加格式变体映射: {mapped_id} -> {variant}")

                    logger.info(f"已加载数据源: {mapped_id} (映射自 {source_id})")
                else:
                    logger.warning(f"数据源不存在: {mapped_id}")
            except Exception as e:
                logger.warning(f"加载数据源 {mapped_id} 失败: {e}")

                # 输出已加载的所有数据源
        logger.info(f"已加载 {len(sources_dict)} 个数据源: {list(sources_dict.keys())}")

        # 如果没有加载到任何数据源，尝试从外部文件夹手动加载CSV文件
        if len(sources_dict) == 0:
            # 尝试从external文件夹直接加载CSV文件作为临时解决方案
            try:
                import pathlib

                import pandas as pd

                from app.core.datasource import create_df_source

                # 使用项目根目录下的external文件夹
                external_dir = pathlib.Path("external")
                if external_dir.exists():
                    # 查找文件夹中的CSV文件
                    for file_path in external_dir.glob("*.csv"):
                        try:
                            # 读取CSV文件
                            df = pd.read_csv(file_path)
                            # 创建数据源
                            file_uuid = file_path.stem
                            source = create_df_source(df, file_uuid)

                            # 添加数据源和它的变种
                            dremio_id = f"dremio_{file_uuid}"
                            dremio_external_id = f"dremio_external_{file_uuid}"
                            dremio_external_csv_id = f"{dremio_external_id}_csv"

                            # 添加所有可能的ID格式
                            sources_dict[file_uuid] = source
                            sources_dict[dremio_id] = source
                            sources_dict[dremio_external_id] = source
                            sources_dict[dremio_external_csv_id] = source

                            logger.info(f"从external文件夹手动加载数据源: {file_path.name} -> {dremio_external_csv_id}")
                        except Exception as e:
                            logger.warning(f"手动加载CSV文件失败: {file_path}, 错误: {e}")
            except Exception as e:
                logger.warning(f"尝试手动加载external文件夹失败: {e}")

        # 创建Sources对象
        sources = Sources(sources_dict)  # 从工作流获取工具调用并执行
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
                    # 获取当前会话中的所有数据源
                    available_session_ids = session.dataset_ids

                    # 如果会话中有数据源，确保使用会话中的数据源
                    if available_session_ids and len(available_session_ids) > 0:
                        # 选择主数据源
                        primary_session_source = available_session_ids[0]
                        logger.info(
                            f"当前会话有 {len(available_session_ids)} 个数据源，主数据源为: {primary_session_source}"
                        )

                        # 提取原始数据源ID的格式信息
                        def extract_id_format(id_str: str) -> tuple[str, str]:
                            # 提取前缀和后缀
                            prefix = ""
                            suffix = ""

                            # 检测前缀
                            if id_str.startswith("dremio_external_"):
                                prefix = "dremio_external_"
                            elif id_str.startswith("dremio_"):
                                prefix = "dremio_"

                            # 检测后缀
                            if id_str.endswith("_csv"):
                                suffix = "_csv"

                            return prefix, suffix

                        # 处理source_id字段 - 保持原格式但使用会话数据源
                        if "source_id" in args:
                            old_id = args["source_id"]

                            # 获取原ID的格式信息
                            prefix, suffix = extract_id_format(old_id)

                            # 提取会话数据源的UUID部分
                            session_uuid = primary_session_source
                            if primary_session_source.startswith("dremio_"):
                                session_uuid = primary_session_source[7:]  # 去除dremio_前缀

                            # 构造新的ID，保持原格式但使用会话数据源的UUID
                            new_id = f"{prefix}{session_uuid}{suffix}"
                            args["source_id"] = new_id
                            logger.info(f"已调整数据源ID (source_id): {old_id} -> {new_id}")

                        # 处理dataset_id字段 - 保持原格式但使用会话数据源
                        if "dataset_id" in args:
                            old_id = args["dataset_id"]

                            # 获取原ID的格式信息
                            prefix, suffix = extract_id_format(old_id)

                            # 提取会话数据源的UUID部分
                            session_uuid = primary_session_source
                            if primary_session_source.startswith("dremio_"):
                                session_uuid = primary_session_source[7:]  # 去除dremio_前缀

                            # 构造新的ID，保持原格式但使用会话数据源的UUID
                            new_id = f"{prefix}{session_uuid}{suffix}"
                            args["dataset_id"] = new_id
                            logger.info(f"已调整数据源ID (dataset_id): {old_id} -> {new_id}")
                    else:
                        # 如果会话中没有数据源，尝试使用映射表
                        logger.warning("当前会话没有数据源，尝试使用映射表")

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
                    # 自动修正数据源ID - 如果dataset_id存在但在sources中不存在
                    if "dataset_id" in args and not sources.exists(args["dataset_id"]):
                        original_id = args["dataset_id"]
                        available_ids = list(sources.sources.keys())

                        # 尝试自动修正数据源ID
                        corrected_id = None

                        # 尝试1：直接检查可用ID中是否存在
                        if original_id in available_ids:
                            corrected_id = original_id

                        # 尝试2：如果是dremio_external类型，尝试转换为dremio_类型
                        elif original_id.startswith("dremio_external_"):
                            base_id = original_id[15:]  # 移除 "dremio_external_" 前缀
                            if base_id.endswith("_csv"):
                                base_id = base_id.removesuffix("_csv")
                            alternative = f"dremio_{base_id}"
                            if alternative in available_ids:
                                corrected_id = alternative

                        # 尝试3：如果是dremio_类型，尝试转换为dremio_external_类型
                        elif original_id.startswith("dremio_"):
                            base_id = original_id[7:]  # 移除 "dremio_" 前缀
                            alternatives = [f"dremio_external_{base_id}", f"dremio_external_{base_id}_csv"]
                            for alt in alternatives:
                                if alt in available_ids:
                                    corrected_id = alt
                                    break

                        # 尝试4：如果有_csv后缀，尝试去掉后缀
                        elif original_id.endswith("_csv"):
                            base_id = original_id.removesuffix("_csv")
                            if base_id in available_ids:
                                corrected_id = base_id

                        # 尝试5：如果没有_csv后缀，尝试添加后缀
                        else:
                            csv_id = f"{original_id}_csv"
                            if csv_id in available_ids:
                                corrected_id = csv_id

                        # 尝试6：不论什么格式，直接尝试原始ID的UUID部分
                        if not corrected_id and "-" in original_id:
                            # 尝试提取UUID部分
                            import re

                            uuid_match = re.search(
                                r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", original_id
                            )
                            if uuid_match:
                                uuid_part = uuid_match.group(1)
                                # 尝试所有可能的格式组合
                                for prefix in ["", "dremio_", "dremio_external_"]:
                                    for suffix in ["", "_csv"]:
                                        potential_id = f"{prefix}{uuid_part}{suffix}"
                                        if potential_id in available_ids:
                                            corrected_id = potential_id
                                            logger.info(f"通过UUID匹配找到数据源: {original_id} -> {corrected_id}")
                                            break
                                    if corrected_id:
                                        break

                        # 自动修正已在上面完成

                        if corrected_id:
                            # 使用修正后的ID
                            args["dataset_id"] = corrected_id
                            logger.info(f"已自动修正数据源ID: {original_id} -> {corrected_id}")

                            # 更新工具调用参数
                            lc_tool_call["args"] = args
                            assistant_response.tool_calls[tool_call_id].args = json.dumps(args)
                        else:
                            # 无法修正ID，报告错误
                            available_ids = list(sources.sources.keys())
                            error_msg = (
                                f"数据源 {original_id} 不存在，且无法自动修正。可用的数据源ID: {available_ids[:10]}"
                                f"{'...(更多)' if len(available_ids) > 10 else ''}"
                            )
                            logger.error(error_msg)
                            # 记录错误
                            assistant_response.tool_calls[tool_call_id].status = "error"
                            assistant_response.tool_calls[tool_call_id].error = error_msg
                            continue

                    # 同样检查source_id参数
                    if "source_id" in args and not sources.exists(args["source_id"]):
                        original_id = args["source_id"]
                        available_ids = list(sources.sources.keys())

                        # 尝试自动修正数据源ID
                        corrected_id = None

                        # 尝试1：直接检查可用ID中是否存在
                        if original_id in available_ids:
                            corrected_id = original_id

                        # 尝试2：如果是dremio_external类型，尝试转换为dremio_类型
                        elif original_id.startswith("dremio_external_"):
                            base_id = original_id[15:]  # 移除 "dremio_external_" 前缀
                            if base_id.endswith("_csv"):
                                base_id = base_id.removesuffix("_csv")
                            alternative = f"dremio_{base_id}"
                            if alternative in available_ids:
                                corrected_id = alternative

                        # 尝试3：如果是dremio_类型，尝试转换为dremio_external_类型
                        elif original_id.startswith("dremio_"):
                            base_id = original_id[7:]  # 移除 "dremio_" 前缀
                            alternatives = [f"dremio_external_{base_id}", f"dremio_external_{base_id}_csv"]
                            for alt in alternatives:
                                if alt in available_ids:
                                    corrected_id = alt
                                    break

                        # 尝试4：如果有_csv后缀，尝试去掉后缀
                        elif original_id.endswith("_csv"):
                            base_id = original_id.removesuffix("_csv")
                            if base_id in available_ids:
                                corrected_id = base_id

                        # 尝试5：如果没有_csv后缀，尝试添加后缀
                        else:
                            csv_id = f"{original_id}_csv"
                            if csv_id in available_ids:
                                corrected_id = csv_id

                        # 尝试6：不论什么格式，直接尝试原始ID的UUID部分
                        if not corrected_id and "-" in original_id:
                            # 尝试提取UUID部分
                            import re

                            uuid_match = re.search(
                                r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", original_id
                            )
                            if uuid_match:
                                uuid_part = uuid_match.group(1)
                                # 尝试所有可能的格式组合
                                for prefix in ["", "dremio_", "dremio_external_"]:
                                    for suffix in ["", "_csv"]:
                                        potential_id = f"{prefix}{uuid_part}{suffix}"
                                        if potential_id in available_ids:
                                            corrected_id = potential_id
                                            logger.info(f"通过UUID匹配找到数据源: {original_id} -> {corrected_id}")
                                            break
                                    if corrected_id:
                                        break

                        if corrected_id:
                            # 使用修正后的ID
                            args["source_id"] = corrected_id
                            logger.info(f"已自动修正数据源ID: {original_id} -> {corrected_id}")

                            # 更新工具调用参数
                            lc_tool_call["args"] = args
                            assistant_response.tool_calls[tool_call_id].args = json.dumps(args)
                        else:
                            # 无法修正ID，报告错误
                            available_ids = list(sources.sources.keys())
                            error_msg = (
                                f"数据源 {original_id} 不存在，且无法自动修正。可用的数据源ID: {available_ids[:10]}"
                                f"{'...(更多)' if len(available_ids) > 10 else ''}"
                            )
                            logger.error(error_msg)
                            # 记录错误
                            assistant_response.tool_calls[tool_call_id].status = "error"
                            assistant_response.tool_calls[tool_call_id].error = error_msg
                            continue

                    # 直接传入字典作为工具调用并捕获结果
                    from langchain_core.messages import ToolMessage

                    # 执行工具调用
                    try:
                        result = resume_tool_call(lc_tool_call, {"sources": sources})
                        result_content = ""  # 初始化result_content变量

                        # 更新工具调用状态为成功
                        assistant_response.tool_calls[tool_call_id].status = "success"

                        # 处理工具返回的结果
                        if isinstance(result, tuple) and len(result) == 2:
                            # 处理可能的图像结果（如analyze_data工具）
                            text_result, artifact = result
                            # 提取文本内容
                            text_content = (
                                text_result.content if isinstance(text_result, ToolMessage) else str(text_result)
                            )

                            # 如果有图像附件，添加到结果中
                            if artifact and isinstance(artifact, dict) and artifact.get("type") == "image":
                                # 构建包含图像的Markdown格式结果
                                image_base64 = artifact.get("base64_data", "")
                                caption = artifact.get("caption", "分析结果图表")

                                # 构建带图像的结果
                                result_content = f"{text_content}\n\n![{caption}](data:image/png;base64,{image_base64})"
                                assistant_response.tool_calls[tool_call_id].result = result_content
                                logger.info("工具调用返回了图像结果")
                            else:
                                # 只返回文本结果
                                result_content = text_content
                                assistant_response.tool_calls[tool_call_id].result = text_content
                        else:
                            # 标准的文本结果处理
                            result_content = result.content if isinstance(result, ToolMessage) else str(result)
                            assistant_response.tool_calls[tool_call_id].result = result_content
                        # 截取结果的前100个字符显示在日志中
                        result_str = str(result_content)
                        is_long_result = len(result_str) > 100
                        truncated_result = result_str[:100] + "..." if is_long_result else result_str
                        logger.info(f"工具调用执行成功: {tool_name}, 结果: {truncated_result}")
                    except Exception as tool_execution_error:
                        # 更新工具调用状态为错误
                        error_msg = str(tool_execution_error)
                        assistant_response.tool_calls[tool_call_id].status = "error"
                        assistant_response.tool_calls[tool_call_id].error = error_msg
                        logger.exception(f"工具 {tool_name} 执行过程中发生错误: {error_msg}")
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
