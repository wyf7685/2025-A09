"""
对话式数据分析接口
"""

import json
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import DataAnalyzerAgent
from app.api.v1.sessions import sessions
from app.api.v1.uploads import datasets
from app.chain.llm import get_chat_model, get_llm
from app.const import STATE_DIR
from app.log import logger

router = APIRouter()

# Agent 实例缓存
agents: dict[str, DataAnalyzerAgent] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str
    dataset_id: str | None = None


async def generate_chat_stream(request: ChatRequest) -> AsyncIterator[str]:
    """生成聊天流响应"""
    try:
        session_id = request.session_id
        user_message = request.message.strip()
        dataset_id = request.dataset_id

        # 基本参数检查
        if not session_id or session_id not in sessions:
            yield json.dumps({"error": "Session not found"})
            return

        if not user_message:
            yield json.dumps({"error": "Message is required"})
            return

        # 获取当前数据集
        if not dataset_id:
            dataset_id = sessions[session_id]["current_dataset"]

        if not dataset_id or dataset_id not in datasets:
            yield json.dumps({"error": "No dataset available"})
            return

        df = datasets[dataset_id]

        # 获取或创建 Agent
        if session_id not in agents:
            agents[session_id] = DataAnalyzerAgent(df, get_llm(), get_chat_model())
            agents[session_id].load_state(STATE_DIR / f"{session_id}.json")

        agent = agents[session_id]

        # 开始时间
        start_time = datetime.now().isoformat()

        # 初始化响应变量
        full_response = ""

        # 流式输出
        async for message in agent.ainvoke(user_message):
            if message.content:
                content = message.content
                if isinstance(content, list):
                    content = "\n".join(str(c) for c in content)
                full_response += content
                yield json.dumps({"type": "chunk", "content": content}) + "\n"

        # 保存状态
        agent.save_state(STATE_DIR / f"{session_id}.json")

        # 记录对话历史
        chat_entry = {
            "timestamp": start_time,
            "user_message": user_message,
            "ai_response": full_response,
            "execution_results": [],
        }

        # 添加执行结果（如果有图表）
        if agent.execution_results:
            chat_entry["execution_results"] = agent.execution_results
            # 发送执行结果
            yield json.dumps({"type": "results", "results": agent.execution_results}) + "\n"

        sessions[session_id]["chat_history"].append(chat_entry)

        # 发送完成信号
        yield json.dumps({"type": "done", "timestamp": datetime.now().isoformat()})

    except Exception as e:
        logger.exception("流式对话分析失败")
        yield json.dumps({"error": str(e)})


@router.post("/chat/stream")
async def chat_analysis_stream(request: ChatRequest) -> StreamingResponse:
    """对话式数据分析（流式输出）"""
    return StreamingResponse(generate_chat_stream(request), media_type="text/event-stream")
