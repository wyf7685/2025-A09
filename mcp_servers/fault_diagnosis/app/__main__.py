"""
FastMCP 故障诊断服务器

提供机器故障诊断和预测维护工具。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server import FastMCP

from .data_source import read_agent_source_data
from .log import LOGGING_CONFIG
from .tools import analyze_fault_patterns, calculate_health_score, fault_vs_normal_analysis, mine_fault_rules

if TYPE_CHECKING:
    import pandas as pd

instructions = """\
此服务器提供机器故障诊断和预测维护工具。

主要功能:
1. 故障特征对比分析 - 识别正常vs故障样本的显著差异特征
2. 健康度评分 - 评估设备当前的健康状态和故障风险
3. 故障规则挖掘 - 从历史数据提取可解释的故障判断规则
4. 故障模式分析 - 将故障聚类，识别不同类型的故障模式

适用场景:
- 机器设备健康监测
- 故障诊断和根因分析
- 预测性维护决策支持
- 故障模式识别和分类

使用建议:
1. 先用 fault_vs_normal_analysis 了解哪些特征与故障相关
2. 用 analyze_fault_patterns 识别故障类型
3. 用 mine_fault_rules 获取具体的判断规则
4. 用 calculate_health_score 评估当前设备健康状况
"""

app = FastMCP(
    name="fault-diagnosis",
    instructions=instructions,
)


async def read_source(source_id: str) -> pd.DataFrame:
    # See app/core/agent/agents/data_analyzer/context.py
    ctx = app.get_context()
    params = ctx.request_context.session.client_params
    client_name = params and params.clientInfo.name
    assert client_name is not None, "Agent Token is required"

    return await read_agent_source_data(client_name, source_id)


@app.tool()
async def fault_vs_normal(source_id: str) -> dict:
    """
    故障与正常样本对比分析

    对比正常样本和故障样本在各个特征上的差异，识别最显著的故障指示特征。
    这是故障诊断的第一步，帮助理解"什么特征异常时容易发生故障"。

    Args:
        source_id: 数据源ID

    Returns:
        dict: 包含以下内容:
            - fault_rate: 故障率
            - top_discriminators: Top3差异最显著的特征
            - all_comparisons: 所有特征的对比结果
            - interpretation: 文字解释

    Example:
        ```python
        result = await fault_vs_normal("machine_data")
        print(result["interpretation"])
        # 输出: "CS偏高45%、RP偏低32%、VOC偏高153% 是故障的主要特征"
        ```
    """
    df = await read_source(source_id)
    return fault_vs_normal_analysis(df)


@app.tool()
async def health_score(source_id: str, sample_index: int | None = None) -> dict:
    """
    计算设备健康度评分

    基于马氏距离计算样本偏离正常状态的程度，输出0-100分的健康度评分。
    分数越高表示越健康，同时识别异常的传感器。

    Args:
        source_id: 数据源ID
        sample_index: 要评估的样本索引（可选，默认为最后一个样本）

    Returns:
        dict: 包含以下内容:
            - health_score: 健康度评分(0-100)
            - risk_level: 风险等级(低/中/高)
            - abnormal_sensors: 异常传感器列表
            - recommendation: 维护建议
            - actual_failure: 该样本是否实际发生故障

    Example:
        ```python
        result = await health_score("machine_data")
        print(f"健康度: {result['health_score']}分")
        print(f"风险等级: {result['risk_level']}")
        print(f"建议: {result['recommendation']}")
        ```
    """
    df = await read_source(source_id)
    return calculate_health_score(df, sample_index)


@app.tool()
async def fault_rules(source_id: str, min_confidence: float = 0.7) -> dict:
    """
    挖掘故障判断规则

    从历史数据中提取可解释的IF-THEN规则，帮助理解"满足什么条件会导致故障"。
    规则基于决策树算法，输出置信度和支持度等统计信息。

    Args:
        source_id: 数据源ID
        min_confidence: 最小置信度阈值(0-1)，默认0.7

    Returns:
        dict: 包含以下内容:
            - rules: 规则列表，每个规则包含:
                - rule: 规则文本(IF ... THEN 故障)
                - confidence: 置信度
                - support: 支持度
                - coverage: 覆盖的故障样本数
            - total_coverage: 所有规则覆盖的故障比例

    Example:
        ```python
        result = await fault_rules("machine_data", min_confidence=0.75)
        for rule in result["rules"]:
            print(rule["rule"])
            print(f"  置信度: {rule['confidence']}, {rule['coverage']}")
        ```
    """
    df = await read_source(source_id)
    return mine_fault_rules(df, min_confidence=min_confidence)


@app.tool()
async def fault_patterns(source_id: str, n_clusters: int = 3) -> dict:
    """
    故障模式聚类分析

    将所有故障样本聚类成不同的故障类型，识别每种类型的特征。
    帮助理解"故障有哪几种模式，每种模式的原因是什么"。

    Args:
        source_id: 数据源ID
        n_clusters: 聚类数量，默认3

    Returns:
        dict: 包含以下内容:
            - fault_patterns: 故障模式列表，每个包含:
                - name: 模式名称
                - count: 该模式的故障数量
                - percentage: 占比
                - characteristics: 特征描述
                - severity: 严重程度
            - insights: 洞察总结

    Example:
        ```python
        result = await fault_patterns("machine_data", n_clusters=3)
        for pattern in result["fault_patterns"]:
            print(f"{pattern['name']}: {pattern['percentage']}")
            print(f"  特征: {pattern['characteristics']}")
            print(f"  严重程度: {pattern['severity']}")
        ```
    """
    df = await read_source(source_id)
    return analyze_fault_patterns(df, n_clusters=n_clusters)


def run_server_sse() -> None:
    import os

    import anyio
    import uvicorn

    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))

    config = uvicorn.Config(
        app.sse_app(),
        host=host,
        port=port,
        log_level="info",
        log_config=LOGGING_CONFIG,
    )
    server = uvicorn.Server(config)
    anyio.run(server.serve)


if __name__ == "__main__":
    run_server_sse()
