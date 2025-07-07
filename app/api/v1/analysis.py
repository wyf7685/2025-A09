"""
自动化数据分析报告接口
"""

import base64
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.api.v1.sessions import sessions
from app.api.v1.uploads import datasets
from app.const import EXPORT_DIR
from app.core.chain.general_analysis import GeneralDataAnalysis, GeneralDataAnalysisInput
from app.core.chain.llm import get_llm
from app.log import logger
from app.utils import run_sync

router = APIRouter()


class AnalysisRequest(BaseModel):
    session_id: str


class ExportReportRequest(BaseModel):
    session_id: str
    format: str = "markdown"  # markdown, pdf, html


@router.post("/analysis/general")
async def general_analysis(request: AnalysisRequest) -> dict[str, Any]:
    """自动化数据分析报告"""
    try:
        session_id = request.session_id

        if not session_id or session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        # 获取当前数据集
        dataset_id = sessions[session_id]["current_dataset"]
        if not dataset_id or dataset_id not in datasets:
            raise HTTPException(status_code=400, detail="No dataset available")

        df = datasets[dataset_id]

        # 创建分析引擎
        llm = await run_sync(get_llm)()
        analysis = GeneralDataAnalysis(llm=llm)

        # 执行分析
        report, figures = await run_sync(analysis.invoke)(GeneralDataAnalysisInput(df=df))

        # 转换图表为 base64
        figure_data = []
        for i, fig_bytes in enumerate(figures):
            figure_data.append(
                {"id": f"fig_{i}", "data": base64.b64encode(fig_bytes).decode("utf-8"), "type": "image/png"}
            )

        # 保存分析结果
        analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "report": report,
            "figures": figure_data,
            "dataset_shape": df.shape,
        }

        sessions[session_id]["analysis_results"].append(analysis_result)

        return {"success": True, "report": report, "figures": figure_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("自动分析失败")
        raise HTTPException(status_code=500, detail=f"General analysis failed: {e}") from e


@router.post("/export/report")
async def export_report(request: ExportReportRequest) -> Response:
    """导出分析报告"""
    try:
        session_id = request.session_id
        report_format = request.format  # markdown, pdf, html

        if not session_id or session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[session_id]

        if not session["analysis_results"]:
            raise HTTPException(status_code=400, detail="No analysis results found")

        # 获取最新的分析结果
        latest_result = session["analysis_results"][-1]
        report_content = latest_result["report"]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_report_{session_id}_{timestamp}"
        filepath = None

        if report_format == "markdown":
            filepath = EXPORT_DIR / f"{filename}.md"
            with filepath.open("w", encoding="utf-8") as f:
                f.write(report_content)
        elif report_format == "html":
            filepath = EXPORT_DIR / f"{filename}.html"
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>分析报告</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
                    h1, h2, h3 {{ color: #333; }}
                    img {{ max-width: 100%; }}
                    pre {{ background: #f5f5f5; padding: 10px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                <h1>数据分析报告</h1>
                <div class="report-content">
                    {report_content}
                </div>
            </body>
            </html>
            """
            with filepath.open("w", encoding="utf-8") as f:
                f.write(html_content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported report format")

        if filepath is None:
            raise HTTPException(status_code=500, detail="Failed to generate report")

        # 读取文件并返回
        with filepath.open("rb") as f:
            content = f.read()

        media_type = "text/markdown" if report_format == "markdown" else "text/html"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filepath.name}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("导出报告失败")
        raise HTTPException(status_code=500, detail=f"Export report failed: {e}") from e
