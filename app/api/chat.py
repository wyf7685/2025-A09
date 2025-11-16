"""
对话式数据分析接口
"""

import json
import tempfile
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.const import REPORT_TEMPLATE_DIR
from app.core.agent.prompts.data_analyzer import PROMPTS as DATA_ANALYZER_PROMPTS
from app.exception import DAAServiceError
from app.log import logger
from app.schemas.chat import ChatEntry, UserChatMessage
from app.schemas.session import Session, SessionID
from app.services.agent import daa_service
from app.services.report_export import markdown_to_pdf, sanitize_filename
from app.services.session import session_service
from app.utils import buffered_stream, escape_tag

from ._depends import CurrentSessionFromBody

router = APIRouter(prefix="/chat", tags=["DataAnalyzerChat"])


class ChatRequest(BaseModel):
    session_id: SessionID
    message: str
    model_id: str = "gemini-2.0-flash"  # deprecated

    @field_validator("message", mode="after")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """验证消息内容是否为空"""
        if not v or not v.strip():
            raise ValueError("Message is required")
        return v.strip()


async def generate_chat_stream(request: ChatRequest, session: Session) -> AsyncIterator[str]:
    """生成聊天流响应"""
    try:
        chat_entry = ChatEntry(user_message=UserChatMessage(content=request.message))

        async with daa_service.use_agent(session) as agent:
            async for event in buffered_stream(agent.stream(request.message), max_buffer_size=10):
                try:
                    msg = event.model_dump_json() + "\n"
                except Exception:
                    logger.exception("转换事件为 JSON 失败")
                else:
                    yield msg

                chat_entry.add_stream_event(event)

            # 设置会话名称
            if len(session.chat_history) < 3:
                session.name = await agent.create_title()
                logger.info(f"设置会话 {session.id} 名称为: {session.name}")

        # 记录对话历史
        chat_entry.merge_text()
        session.chat_history.append(chat_entry)
        await session_service.save_session(session)

        # 发送完成信号
        yield json.dumps({"type": "done", "timestamp": datetime.now().isoformat()})

    except DAAServiceError as e:
        logger.warning(e)
        yield json.dumps({"error": str(e)})

    except Exception as e:
        logger.exception("流式对话分析失败")
        yield json.dumps({"error": f"流式对话分析失败: {e!r}"})


@router.post("/stream")
async def chat_analysis_stream(request: ChatRequest, session: CurrentSessionFromBody) -> StreamingResponse:
    """对话式数据分析（流式输出）"""
    return StreamingResponse(generate_chat_stream(request, session), media_type="text/event-stream")


class SummaryResponse(BaseModel):
    session_id: SessionID
    summary: str
    figures: list[str]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


@router.post("/summary")
async def chat_summary(session: CurrentSessionFromBody) -> SummaryResponse:
    """获取对话摘要"""
    try:
        async with daa_service.use_agent(session) as agent:
            summary, figures = await agent.summary()
            return SummaryResponse(
                session_id=session.id,
                summary=summary,
                figures=figures,
            )
    except DAAServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except Exception as e:
        logger.exception("生成对话摘要失败")
        raise HTTPException(status_code=500, detail=f"生成对话摘要失败: {e!r}") from e


# 报告模板相关模型
class ReportTemplate(BaseModel):
    """报告模板模型"""

    id: str
    name: str
    description: str
    content: str
    is_default: bool = False
    created_at: str


@router.get("/templates", response_model=list[ReportTemplate])
async def list_templates() -> list[ReportTemplate]:
    """获取所有报告模板"""
    try:
        templates: list[ReportTemplate] = []

        # 添加默认模板
        default_template = ReportTemplate(
            id="default",
            name="默认分析报告模板",
            description="系统内置的标准数据分析报告模板",
            content=DATA_ANALYZER_PROMPTS.default_report_template,
            is_default=True,
            created_at="2024-01-01T00:00:00",
        )
        templates.append(default_template)

        # 加载自定义模板
        for template_file in REPORT_TEMPLATE_DIR.glob("*.txt"):
            try:
                template_content = template_file.read_text(encoding="utf-8")
                lines = template_content.split("\n", 2)
                if len(lines) >= 3:
                    template_name = lines[0].removeprefix("# 模板名称:").strip()
                    template_desc = lines[1].removeprefix("# 模板描述:").strip()
                    template_prompt = lines[2]

                    template = ReportTemplate(
                        id=template_file.stem,
                        name=template_name,
                        description=template_desc,
                        content=template_prompt,
                        is_default=False,
                        created_at=str(datetime.fromtimestamp(template_file.stat().st_ctime)),
                    )
                    templates.append(template)
            except Exception as e:
                logger.warning(f"加载模板失败 {template_file}: {e}")

        return templates
    except Exception as e:
        logger.error(f"获取模板列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取模板列表失败") from e


@router.post("/templates/upload")
async def upload_template(
    template_name: str = Form(),
    template_description: str = Form(),
    template_file: UploadFile = File(),
) -> dict[str, Any]:
    """上传自定义报告模板"""
    try:
        if not template_file.filename:
            raise HTTPException(status_code=400, detail="请上传有效的模板文件")

        if not template_file.filename.endswith(".txt") or not template_file.filename.endswith(".md"):
            raise HTTPException(status_code=400, detail="只支持.txt或.md格式的模板文件")

        template_content = (await template_file.read()).decode("utf-8")
        template_id = f"custom_{uuid.uuid4().hex[:8]}"
        template_file_path = REPORT_TEMPLATE_DIR / f"{template_id}.txt"

        formatted_content = f"# 模板名称: {template_name}\n# 模板描述: {template_description}\n{template_content}"
        template_file_path.write_text(formatted_content, encoding="utf-8")

        logger.info(f"上传自定义模板: {template_name} ({template_id})")

        return {
            "id": template_id,
            "name": template_name,
            "description": template_description,
        }
    except Exception as e:
        logger.error(f"上传模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传模板失败: {e}") from e


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str) -> None:
    """删除自定义模板"""
    try:
        if template_id == "default":
            raise HTTPException(status_code=400, detail="不能删除默认模板")

        template_file = REPORT_TEMPLATE_DIR / f"{template_id}.txt"
        if not template_file.exists():
            raise HTTPException(status_code=404, detail="模板不存在")

        template_file.unlink()
        logger.info(f"删除模板: {template_id}")

        return
    except Exception as e:
        logger.error(f"删除模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除模板失败: {e}") from e


class GenerateReportRequest(BaseModel):
    """生成报告请求"""

    session_id: str
    template_id: str | None = None
    model_id: str | None = None  # deprecated


class GenerateReportResponse(BaseModel):
    """生成报告响应"""

    session_id: str
    report: str
    figures: list[str]
    template_used: str
    report_title: str


@router.post("/generate-report")
async def generate_report(request: GenerateReportRequest, session: CurrentSessionFromBody) -> GenerateReportResponse:
    """生成分析报告（基于现有的summary功能）"""
    try:
        # 获取模板内容
        template_content = None
        template_name = "默认模板"

        if request.template_id and request.template_id != "default":
            template_file = REPORT_TEMPLATE_DIR / f"{request.template_id}.txt"
            if not template_file.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"自定义模板 {request.template_id} 不存在，请检查模板ID是否正确",
                )

            try:
                template_file_content = template_file.read_text(encoding="utf-8")
                lines = template_file_content.split("\n", 2)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"自定义模板 {request.template_id} 读取失败: {e}",
                ) from e

            if len(lines) < 3 or not lines[0].startswith("# 模板名称:") or not lines[1].startswith("# 模板描述:"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"自定义模板 {request.template_id} 格式不正确，必须包含名称和描述",
                )

            template_name = lines[0].removeprefix("# 模板名称:").strip()
            template_content = lines[2]
            logger.opt(colors=True).info(
                f"使用自定义模板: <y>{escape_tag(template_name)}</> <c>({escape_tag(request.template_id)})</>"
            )

        async with daa_service.use_agent(session) as agent:
            # 检查是否有对话历史
            if not agent.has_messages():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前会话没有对话记录，请先进行数据分析对话",
                )

            # 生成报告内容
            summary, figures = await agent.summary(template_content)

            # 生成报告标题
            report_title = await agent.create_title()
            logger.info(f"生成报告标题: {report_title}")

        return GenerateReportResponse(
            session_id=session.id,
            report=summary,
            figures=figures,
            template_used=template_name,
            report_title=report_title,
        )

    except HTTPException:
        raise
    except DAAServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=f"生成分析报告失败: {e}") from e
    except Exception as e:
        logger.exception("生成分析报告失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成分析报告失败: {e}",
        ) from e


class DownloadReportRequest(BaseModel):
    """下载报告请求"""

    report_content: str
    report_title: str
    figures: list[str] = []  # Base64编码的图片列表


@router.post("/download-report-pdf")
async def download_report_pdf(request: DownloadReportRequest) -> StreamingResponse:
    """下载 PDF 格式的报告"""
    try:
        # 清理文件名
        safe_filename = sanitize_filename(request.report_title)
        if not safe_filename:
            safe_filename = "分析报告"

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            # 替换图片占位符
            report_content = request.report_content
            for i, figure_data in enumerate(request.figures):
                # 确保 figure_data 是完整的 data:image 格式
                if not figure_data.startswith("data:image"):
                    figure_data = f"data:image/png;base64,{figure_data}"

                # 尝试替换多种占位符格式
                placeholders = [
                    f"{{{{figure-{i}}}}}",  # {{figure-0}}
                    f"{{figure-{i}}}",  # {figure-0}
                ]

                replaced = False
                for placeholder in placeholders:
                    if placeholder in report_content:
                        report_content = report_content.replace(placeholder, figure_data)
                        logger.info(f"替换图片占位符: {placeholder}")
                        replaced = True
                        break

                if not replaced:
                    logger.warning(f"未找到图片占位符 figure-{i}，尝试的格式: {placeholders}")

            # 转换为 PDF
            markdown_to_pdf(report_content, tmp_path)

            # 读取 PDF 文件
            pdf_content = tmp_path.read_bytes()

            # 删除临时文件
            tmp_path.unlink()

            # 对文件名进行 URL 编码（RFC 5987 格式）
            encoded_filename = quote(f"{safe_filename}.pdf")

            # 返回 PDF 文件
            return StreamingResponse(
                iter([pdf_content]),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                    "Content-Type": "application/pdf",
                },
            )
        except Exception:
            # 确保删除临时文件
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    except Exception as e:
        logger.exception("下载报告失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载报告失败: {e}",
        ) from e
