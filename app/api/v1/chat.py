"""
对话式数据分析接口
"""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.const import DATA_DIR
from app.core.agent.agents.data_analyzer import SUMMARY_PROMPT
from app.log import logger
from app.schemas.chat import ChatEntry, UserChatMessage
from app.schemas.session import SessionID
from app.services.agent import AgentInUse, AgentNotFound, daa_service
from app.services.session import session_service

router = APIRouter(prefix="/chat")

# 模板存储目录
TEMPLATES_DIR = DATA_DIR / "report_templates"
TEMPLATES_DIR.mkdir(exist_ok=True)


class ChatRequest(BaseModel):
    session_id: SessionID
    message: str
    model_id: str = "gemini-2.0-flash"  # 默认模型

    @field_validator("message", mode="after")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """验证消息内容是否为空"""
        if not v or not v.strip():
            raise ValueError("Message is required")
        return v.strip()


async def generate_chat_stream(request: ChatRequest) -> AsyncIterator[str]:
    """生成聊天流响应"""
    session = session_service.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_id = session.id

    try:
        async with daa_service.use_agent(session, request.model_id, create_if_non_exist=True) as agent:
            # 初始化响应变量
            chat_entry = ChatEntry(user_message=UserChatMessage(content=request.message))

            # 流式输出
            async for event in agent.astream(request.message):
                try:
                    msg = event.model_dump_json() + "\n"
                except Exception:
                    logger.exception("转换事件为 JSON 失败")
                else:
                    yield msg

                chat_entry.add_stream_event(event)

            chat_entry.merge_text()

            # 如果这是第一条消息，设置会话名称
            if len(session.chat_history) == 0:
                session.name = await agent.create_title_async()
                logger.info(f"设置会话 {session_id} 名称为: {session.name}")

        # 记录对话历史
        session.chat_history.append(chat_entry)
        session_service.save_session(session)

        # 发送完成信号
        yield json.dumps({"type": "done", "timestamp": datetime.now().isoformat()})

    except AgentInUse:
        logger.warning(f"会话 {session.id} 的 Agent 正在使用中")
        yield json.dumps({"error": f"会话 {session.id} 的 Agent 正在使用中"})

    except Exception as e:
        logger.exception("流式对话分析失败")
        yield json.dumps({"error": str(e)})


@router.post("/stream")
async def chat_analysis_stream(request: ChatRequest) -> StreamingResponse:
    """对话式数据分析（流式输出）"""
    return StreamingResponse(generate_chat_stream(request), media_type="text/event-stream")


class SummaryRequest(BaseModel):
    session_id: SessionID
    model_id: str | None = None


class SummaryResponse(BaseModel):
    session_id: SessionID
    summary: str
    figures: list[str]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


@router.post("/summary")
async def chat_summary(request: SummaryRequest) -> SummaryResponse:
    """获取对话摘要"""
    session = session_service.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        async with daa_service.use_agent(session, request.model_id, create_if_non_exist=False) as agent:
            summary, figures = await agent.summary_async()
            return SummaryResponse(
                session_id=session.id,
                summary=summary,
                figures=figures,
            )
    except AgentInUse:
        raise HTTPException(status_code=503, detail="Agent is currently in use, please try again later") from None
    except AgentNotFound:
        raise HTTPException(status_code=404, detail="Agent not found for this session") from None
    except Exception as e:
        logger.exception("获取对话摘要失败")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {e}") from e


# 报告模板相关模型
class ReportTemplate(BaseModel):
    """报告模板模型"""

    id: str
    name: str
    description: str
    content: str
    is_default: bool = False
    created_at: str


class GenerateReportRequest(BaseModel):
    """生成报告请求"""

    session_id: str
    template_id: str | None = None
    model_id: str | None = None


class GenerateReportResponse(BaseModel):
    """生成报告响应"""

    session_id: str
    report: str
    figures: list[str]
    template_used: str


@router.get("/templates")
async def list_templates() -> dict[str, Any]:
    """获取所有报告模板"""
    try:
        templates = []

        # 添加默认模板
        default_template = ReportTemplate(
            id="default",
            name="默认分析报告模板",
            description="系统内置的标准数据分析报告模板",
            content=SUMMARY_PROMPT,
            is_default=True,
            created_at="2024-01-01T00:00:00",
        )
        templates.append(default_template.model_dump())

        # 加载自定义模板
        for template_file in TEMPLATES_DIR.glob("*.txt"):
            try:
                template_content = template_file.read_text(encoding="utf-8")
                lines = template_content.split("\n", 2)
                if len(lines) >= 3:
                    template_name = lines[0].replace("# 模板名称:", "").strip()
                    template_desc = lines[1].replace("# 模板描述:", "").strip()
                    template_prompt = lines[2]

                    template = ReportTemplate(
                        id=template_file.stem,
                        name=template_name,
                        description=template_desc,
                        content=template_prompt,
                        is_default=False,
                        created_at=str(datetime.fromtimestamp(template_file.stat().st_ctime)),
                    )
                    templates.append(template.model_dump())
            except Exception as e:
                logger.warning(f"加载模板失败 {template_file}: {e}")

        return {"success": True, "templates": templates, "count": len(templates)}
    except Exception as e:
        logger.error(f"获取模板列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取模板列表失败") from e


@router.post("/templates/upload")
async def upload_template(
    template_name: str = Form(...), template_description: str = Form(...), template_file: UploadFile = File(...)
) -> dict[str, Any]:
    """上传自定义报告模板"""
    try:
        if not template_file.filename:
            raise HTTPException(status_code=400, detail="请上传有效的模板文件")

        if not template_file.filename.endswith(".txt"):
            raise HTTPException(status_code=400, detail="只支持.txt格式的模板文件")

        template_content = (await template_file.read()).decode("utf-8")
        template_id = f"custom_{uuid.uuid4().hex[:8]}"
        template_file_path = TEMPLATES_DIR / f"{template_id}.txt"

        formatted_content = f"# 模板名称: {template_name}\n# 模板描述: {template_description}\n{template_content}"
        template_file_path.write_text(formatted_content, encoding="utf-8")

        logger.info(f"上传自定义模板: {template_name} ({template_id})")

        return {
            "success": True,
            "message": "模板上传成功",
            "template": {"id": template_id, "name": template_name, "description": template_description},
        }
    except Exception as e:
        logger.error(f"上传模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传模板失败: {e}") from e


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str) -> dict[str, Any]:
    """删除自定义模板"""
    try:
        if template_id == "default":
            raise HTTPException(status_code=400, detail="不能删除默认模板")

        template_file = TEMPLATES_DIR / f"{template_id}.txt"
        if not template_file.exists():
            raise HTTPException(status_code=404, detail="模板不存在")

        template_file.unlink()
        logger.info(f"删除模板: {template_id}")

        return {"success": True, "message": "模板删除成功"}
    except Exception as e:
        logger.error(f"删除模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除模板失败: {e}") from e


@router.post("/generate-report")
async def generate_report(request: GenerateReportRequest) -> GenerateReportResponse:
    """生成分析报告（基于现有的summary功能）"""
    session = session_service.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # 获取模板内容
        template_content = SUMMARY_PROMPT
        template_name = "默认模板"

        if request.template_id and request.template_id != "default":
            template_file = TEMPLATES_DIR / f"{request.template_id}.txt"
            if template_file.exists():
                try:
                    template_file_content = template_file.read_text(encoding="utf-8")
                    lines = template_file_content.split("\n", 2)
                    if len(lines) >= 3:
                        template_name = lines[0].replace("# 模板名称:", "").strip()
                        template_content = lines[2]
                except Exception as e:
                    logger.warning(f"读取自定义模板失败，使用默认模板: {e}")

        async with daa_service.use_agent(session, request.model_id, create_if_non_exist=True) as agent:
            # 检查是否有对话历史
            messages = agent.get_messages()
            if not messages:
                # 如果没有对话历史，返回提示信息
                return GenerateReportResponse(
                    session_id=session.id,
                    report="## 暂无分析内容\n\n"
                    "当前会话还没有进行任何数据分析对话。请先在此会话中与AI进行数据分析对话，然后再生成报告。",
                    figures=[],
                    template_used=template_name,
                )

            if request.template_id and request.template_id != "default":
                # 使用自定义模板（临时修改agent的summary方法）
                from langchain.prompts import PromptTemplate

                from app.core.agent.agents.data_analyzer import format_conversation

                # 获取对话消息
                conversation, figures = format_conversation(messages, include_figures=True)

                # 使用自定义模板生成提示
                prompt = PromptTemplate(template=template_content, input_variables=["conversation"])
                summary = (prompt | agent.llm).invoke({"conversation": conversation})
            else:
                # 使用默认模板
                summary, figures = await agent.summary_async()

            return GenerateReportResponse(
                session_id=session.id, report=summary, figures=figures, template_used=template_name
            )
    except AgentInUse:
        raise HTTPException(status_code=503, detail="Agent is currently in use, please try again later") from None
    except AgentNotFound:
        raise HTTPException(status_code=404, detail="Agent not found for this session") from None
    except Exception as e:
        logger.exception("生成分析报告失败")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}") from e
