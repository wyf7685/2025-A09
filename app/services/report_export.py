"""
报告导出服务 - 支持 Markdown 到 PDF 的转换
"""

import base64
import contextlib
import re
import sys
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _process_image(image_data: str | bytes | Path, max_width: float = 15 * cm) -> Image | None:
    """
    处理图片数据并创建 ReportLab Image 对象

    Args:
        image_data: 图片数据，可以是:
            - Base64 编码字符串 (data:image/...;base64,...)
            - 文件路径 (Path 或 str)
            - HTTP/HTTPS URL
            - 字节数据 (bytes)
        max_width: 图片最大宽度

    Returns:
        ReportLab Image 对象，如果处理失败则返回 None
    """

    from app.log import logger

    try:
        img_buffer = None
        img = None

        # 处理 Base64 编码的图片
        if isinstance(image_data, str):
            if image_data.startswith("data:image"):
                logger.info("处理Base64编码图片")
                # 提取 base64 数据
                base64_data = image_data.split(",", 1)[1] if "," in image_data else image_data
                img_bytes = base64.b64decode(base64_data)
                img_buffer = BytesIO(img_bytes)
            elif Path(image_data).exists():
                logger.info(f"读取本地文件: {image_data}")
                # 文件路径
                image_data = Path(image_data)
            else:
                # 尝试作为相对路径
                logger.info(f"尝试相对路径: {image_data}")
                possible_path = Path(image_data)
                if possible_path.exists():
                    image_data = possible_path
                else:
                    logger.warning(f"图片路径不存在: {image_data}")
                    return None

        # 处理文件路径
        if isinstance(image_data, Path) and image_data.exists():
            img = Image(str(image_data))
        # 处理字节数据
        elif isinstance(image_data, bytes):
            img_buffer = BytesIO(image_data)
            img = Image(img_buffer)
        # 处理 BytesIO 对象
        elif img_buffer:
            img = Image(img_buffer)

        if img is None:
            logger.warning("无法创建图片对象")
            return None

        # 调整图片大小
        if img.drawWidth > max_width:
            aspect = img.drawHeight / img.drawWidth
            img.drawWidth = max_width
            img.drawHeight = max_width * aspect

        logger.info(f"图片处理成功: {img.drawWidth} x {img.drawHeight}")
        return img
    except Exception as e:
        logger.warning(f"处理图片失败: {e}", exc_info=True)
        return None


def _extract_plotly_chart(code_block: str) -> str | None:
    """
    从代码块中提取 Plotly 图表的 Base64 数据

    Args:
        code_block: 代码块内容

    Returns:
        Base64 编码的图片数据，如果没有找到则返回 None
    """
    # 查找 Plotly 图表的 Base64 数据
    # 格式: ![plotly](data:image/png;base64,...)
    match = re.search(r"!\[.*?\]\((data:image/[^;]+;base64,[^)]+)\)", code_block)
    if match:
        return match.group(1)

    # 或者直接是 data:image 格式
    match = re.search(r"(data:image/[^;]+;base64,[^\s]+)", code_block)
    if match:
        return match.group(1)

    return None


def _register_chinese_fonts() -> str:
    """
    注册中文字体（如果可用）

    Returns:
        可用的中文字体名称
    """
    if sys.platform == "win32":
        # Windows 字体目录
        font_dirs = [
            Path("C:\\Windows\\Fonts"),
            Path("~\\AppData\\Local\\Microsoft\\Windows\\Fonts").expanduser(),
        ]
    elif sys.platform == "darwin":
        # macOS 字体目录
        font_dirs = [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            Path("~/Library/Fonts").expanduser(),
        ]
    else:
        # Linux 字体目录
        font_dirs = [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path("~/.fonts").expanduser(),
            Path("~/.local/share/fonts").expanduser(),
        ]

    # 尝试的字体列表（按优先级）
    font_candidates = [
        ("SimHei", "simhei.ttf"),  # 黑体
        ("SimSun", "simsun.ttc"),  # 宋体
        ("Microsoft YaHei", "msyh.ttc"),  # 微软雅黑
        ("Microsoft YaHei", "msyhbd.ttc"),  # 微软雅黑粗体
        ("SimHei", "simhei.ttf"),  # 黑体
        ("Noto Sans CJK SC", "NotoSansCJKsc-Regular.otf"),  # 思源黑体简体
        ("WenQuanYi Zen Hei", "WenQuanYiZenHei.ttf"),  # 文泉驿正黑
    ]

    registered_font = None

    for font_name, font_file in font_candidates:
        for font_dir in map(Path, font_dirs):
            if (font_path := font_dir / font_file).exists():
                with contextlib.suppress(Exception):
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    registered_font = font_name
                    break
        if registered_font:
            break

    return registered_font or "Helvetica"


def _parse_markdown_to_elements(markdown_content: str, styles: dict, chinese_font: str = "Helvetica") -> list:
    """
    解析 Markdown 内容为 ReportLab 元素

    Args:
        markdown_content: Markdown 格式的内容
        styles: 样式字典
        chinese_font: 中文字体名称

    Returns:
        ReportLab 元素列表
    """
    elements = []
    lines = markdown_content.split("\n")
    in_code_block = False
    code_lines = []
    code_type = ""
    table_lines = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        # 处理代码块
        if stripped.startswith("```"):
            if in_code_block:
                # 结束代码块
                code_content = "\n".join(code_lines)

                # 检查是否是图表代码块（plotly、matplotlib等）
                if code_type.lower() in ["plotly", "matplotlib", "chart"]:
                    # 尝试提取图表的 Base64 数据
                    chart_data = _extract_plotly_chart(code_content)
                    if chart_data:
                        img = _process_image(chart_data)
                        if img:
                            elements.append(img)
                            elements.append(Spacer(1, 0.3 * cm))
                        else:
                            # 如果图片处理失败，显示为代码
                            elements.append(Paragraph(f"<font name='Courier'>{code_content}</font>", styles["Code"]))
                            elements.append(Spacer(1, 0.3 * cm))
                    else:
                        # 没有找到图表数据，显示为代码
                        elements.append(Paragraph(f"<font name='Courier'>{code_content}</font>", styles["Code"]))
                        elements.append(Spacer(1, 0.3 * cm))
                else:
                    # 普通代码块
                    elements.append(Paragraph(f"<font name='Courier'>{code_content}</font>", styles["Code"]))
                    elements.append(Spacer(1, 0.3 * cm))

                code_lines = []
                code_type = ""
                in_code_block = False
            else:
                # 开始代码块，记录代码类型
                code_type = stripped[3:].strip()
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # 处理表格
        if "|" in stripped and stripped.count("|") >= 2:
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(stripped)
            continue

        if in_table:
            # 表格结束
            if table_lines:
                table = _create_table_from_markdown(table_lines, chinese_font)
                if table:
                    elements.append(table)
                    elements.append(Spacer(1, 0.3 * cm))
            table_lines = []
            in_table = False

        # 处理 Markdown 图片 ![alt](url)
        img_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if img_match:
            alt_text = img_match.group(1)
            img_url = img_match.group(2)
            img = _process_image(img_url)
            if img:
                elements.append(img)
                elements.append(Spacer(1, 0.3 * cm))
                # 如果有 alt 文本，添加图片说明
                if alt_text:
                    elements.append(Paragraph(f"<i>{alt_text}</i>", styles["Normal"]))
                    elements.append(Spacer(1, 0.2 * cm))
            continue

        # 处理标题
        if stripped.startswith("# "):
            elements.append(Paragraph(stripped[2:], styles["Heading1"]))
            elements.append(Spacer(1, 0.5 * cm))
        elif stripped.startswith("## "):
            elements.append(Paragraph(stripped[3:], styles["Heading2"]))
            elements.append(Spacer(1, 0.4 * cm))
        elif stripped.startswith("### "):
            elements.append(Paragraph(stripped[4:], styles["Heading3"]))
            elements.append(Spacer(1, 0.3 * cm))
        # 处理列表
        elif stripped.startswith(("- ", "* ")):
            # 使用简单的符号，确保中文字体支持
            list_text = stripped[2:]
            # 使用 · (中点) 或 ○ (空心圆) 或 ● (实心圆) 替代项目符号
            elements.append(Paragraph(f"· {list_text}", styles["Normal"]))
        elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1:3] in (". ", ") "):
            elements.append(Paragraph(stripped, styles["Normal"]))
        # 处理分隔线
        elif stripped in ("---", "***", "___"):
            elements.append(Spacer(1, 0.5 * cm))
        # 处理普通段落
        elif stripped:
            # 处理粗体和斜体
            text = stripped.replace("**", "<b>").replace("__", "<b>")
            text = text.replace("*", "<i>").replace("_", "<i>")
            elements.append(Paragraph(text, styles["Normal"]))
            elements.append(Spacer(1, 0.2 * cm))
        else:
            # 空行
            elements.append(Spacer(1, 0.2 * cm))

    return elements


def _create_table_from_markdown(table_lines: list[str], chinese_font: str = "Helvetica") -> Table | None:
    """从 Markdown 表格行创建 ReportLab 表格"""
    if len(table_lines) < 2:
        return None

    # 解析表格数据
    data = []
    for i, line in enumerate(table_lines):
        if i == 1 and all(c in "-:|" for c in line.strip()):
            # 跳过分隔行
            continue
        cells = [cell.strip() for cell in line.split("|")]
        cells = [c for c in cells if c]  # 移除空单元格
        if cells:
            data.append(cells)

    if not data:
        return None

    # 创建表格
    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), chinese_font),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                ("FONTNAME", (0, 1), (-1, -1), chinese_font),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("TOPPADDING", (0, 1), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ]
        )
    )
    return table


def markdown_to_pdf(markdown_content: str, output_path: Path | str) -> None:
    """
    将 Markdown 内容转换为 PDF 文件

    Args:
        markdown_content: Markdown 格式的内容
        output_path: 输出 PDF 文件的路径
    """
    # 注册中文字体并获取字体名
    chinese_font = _register_chinese_fonts()

    # 创建 PDF 文档
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    # 获取样式
    styles_base = getSampleStyleSheet()

    # 自定义样式（使用中文字体）
    styles = {
        "Heading1": ParagraphStyle(
            "CustomHeading1",
            parent=styles_base["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#2c3e50"),
            spaceAfter=12,
            fontName=chinese_font,
        ),
        "Heading2": ParagraphStyle(
            "CustomHeading2",
            parent=styles_base["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#34495e"),
            spaceAfter=10,
            fontName=chinese_font,
        ),
        "Heading3": ParagraphStyle(
            "CustomHeading3",
            parent=styles_base["Heading3"],
            fontSize=12,
            textColor=colors.HexColor("#7f8c8d"),
            spaceAfter=8,
            fontName=chinese_font,
        ),
        "Normal": ParagraphStyle(
            "CustomNormal",
            parent=styles_base["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#333333"),
            fontName=chinese_font,
        ),
        "Code": ParagraphStyle(
            "CustomCode",
            parent=styles_base["Code"],
            fontSize=9,
            leftIndent=10,
            rightIndent=10,
            backColor=colors.HexColor("#f8f8f8"),
            borderColor=colors.HexColor("#dddddd"),
            borderWidth=1,
            borderPadding=5,
            fontName=chinese_font,
        ),
    }

    # 解析 Markdown 并构建元素
    elements = _parse_markdown_to_elements(markdown_content, styles, chinese_font)

    # 生成 PDF
    doc.build(elements)


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除不合法字符

    Args:
        filename: 原始文件名

    Returns:
        清理后的文件名
    """
    # 移除不合法字符
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # 移除首尾空格
    filename = filename.strip()
    # 限制长度
    if len(filename) > 200:
        filename = filename[:200]
    return filename
