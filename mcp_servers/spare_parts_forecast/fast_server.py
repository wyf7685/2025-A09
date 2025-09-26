"""FastMCP based server for spare parts forecasting.

Run (package mode):
    python -m mcp_servers.spare_parts_forecast.fast_server
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mcp.server import FastMCP
from mcp.server.fastmcp import Image

from .data_source import read_agent_source_data

if TYPE_CHECKING:
    import pandas as pd


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

instructions = """\
此服务器提供多种备件需求预测算法:

可用算法分类和功能:
- 统计类: SMA(简单移动平均), EMA(指数平滑), Croston(间歇需求), ARIMA
- 机器学习: 随机森林, XGBoost
- 深度学习: BP神经网络

主要工具:
- algorithms: 列出所有可用算法
- algorithm_categories: 按类别显示算法列表
- sma_forecast: 简单移动平均预测
- ema_forecast: 指数平滑预测
- croston_forecast: 间歇需求预测
- arima_forecast: ARIMA预测
- forest_forecast: 随机森林预测
- xgb_forecast: XGBoost预测
- bp_forecast: BP神经网络预测

对于大多数算法,可通过参数n指定预测步数。机器学习算法可通过column_index指定预测列。
"""

app = FastMCP(
    name="spare-parts-forecast-fast",
    instructions=instructions,
)


def create_fast_server() -> FastMCP:
    """Factory returning FastMCP app (for embedding)."""
    return app


__all__ = [
    "algorithm_categories",
    "algorithms",
    "arima_forecast",
    "bp_forecast",
    "create_fast_server",
    "croston_forecast",
    "ema_forecast",
    "forest_forecast",
    "sma_forecast",
    "xgb_forecast",
]

from .forecasting import (
    arima_forecast_impl,
    croston_forecast_try,
    ema_forecast_try,
    forest_try,
    get_available_algorithms,
    list_algorithms,
    sma_forecast_try,
    xgboost_forecast,
    zero_and_bp_predict,
)


def read_source(source_id: str) -> pd.DataFrame:
    # See app/core/agent/agents/data_analyzer/context.py
    ctx = app.get_context()
    params = ctx.request_context.session.client_params
    client_name = params and params.clientInfo.name
    assert client_name is not None, "Session ID is required"

    return read_agent_source_data(client_name, source_id)


@app.tool()
def algorithms() -> list[str]:
    """列出所有算法名称"""
    return list_algorithms()


@app.tool()
def algorithm_categories() -> dict[str, list[str]]:
    """按类别列出可用算法"""
    return get_available_algorithms()


@app.tool()
def sma_forecast(source_id: str, n: int = 4) -> Any:
    """SMA 简单移动平均预测"""
    df = read_source(source_id)
    return sma_forecast_try(n, df)


@app.tool()
def ema_forecast(source_id: str, n: int = 4) -> Any:
    """EMA 指数平滑预测"""
    df = read_source(source_id)
    return ema_forecast_try(n, df)


@app.tool()
def croston_forecast(source_id: str, n: int = 4) -> Any:
    """Croston 间歇需求预测"""
    df = read_source(source_id)
    return croston_forecast_try(n, df)


@app.tool(structured_output=False)
def arima_forecast(  # noqa: ANN201
    source_id: str,
    target_column: str,
    time_column: str = "time",
    arima_order_p: int = 2,
    arima_order_d: int = 1,
    arima_order_q: int = 1,
    confidence_level: float = 0.95,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
    plot_title: str | None = None,
):
    """
    ARIMA时间序列预测分析

    执行ARIMA(自回归积分移动平均)模型预测，提供详细的统计分析和诊断信息。
    包括平稳性检验、模型拟合、预测评估和残差分析等完整流程。

    Args:
        source_id: 数据源ID，用于获取预测数据
        target_column: 目标预测列名，指定要预测的数据列
        time_column: 时间列名，默认为"time"
        arima_order_p: ARIMA模型的自回归阶数(p)，默认为2
        arima_order_d: ARIMA模型的差分阶数(d)，默认为1
        arima_order_q: ARIMA模型的移动平均阶数(q)，默认为1
        confidence_level: 预测置信水平，取值范围0-1，默认为0.95(95%置信区间)
        enable_diagnostics: 是否启用详细诊断分析和图表生成，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值
        plot_title: 图表标题，默认为None(自动生成)

    Returns:
        ARIMAAnalysisResult | tuple[ARIMAAnalysisResult, Image]: 包含以下键值的分析结果字典:
            - target_column: 预测目标列名
            - arima_order: ARIMA模型参数(p,d,q)
            - total_samples: 总样本数
            - train_samples: 训练样本数
            - test_samples: 测试样本数
            - mape: 平均绝对百分比误差(%)
            - mae: 平均绝对误差
            - rmse: 均方根误差
            - r_squared: 决定系数
            - adf_p_value: ADF平稳性检验p值
            - is_stationary: 序列是否平稳
            - model_aic: 模型AIC信息准则
            - model_bic: 模型BIC信息准则
            - convergence_status: 模型是否收敛
            - actual_values: 实际观测值列表
            - predicted_values: 预测值列表
            - prediction_intervals: 预测置信区间(如果启用诊断)
            - execution_time: 执行时间(秒)
            - warnings: 警告信息列表
            启用诊断模式时,还会返回图表

    Raises:
        ValueError: 当指定的列不存在或数据格式错误时
        RuntimeError: 当模型拟合失败或预测过程出错时

    Example:
        基础预测:
        ```
        result = arima_forecast("data_001", "demand_quantity")
        print(f"预测MAPE: {result['mape']:.2f}%")
        ```

        自定义参数预测:
        ```
        result = arima_forecast(
            source_id="data_001",
            target_column="sales_volume",
            time_column="date",
            arima_order_p=1,
            arima_order_d=1,
            arima_order_q=2,
            confidence_level=0.90,
            plot_title="销量预测分析"
        )
        ```

    Note:
        - ARIMA模型适用于平稳或经差分后平稳的时间序列
        - 参数(p,d,q)分别表示自回归项数、差分次数、移动平均项数
        - 启用诊断模式会生成详细的残差分析图表
        - 预测结果包含置信区间，用于评估预测的不确定性
        - 执行时间取决于数据量大小和模型复杂度
    """
    df = read_source(source_id)

    # 调用ARIMA预测函数
    result, image_bytes = arima_forecast_impl(
        df=df,
        target_column=target_column,
        time_column=time_column,
        arima_order=(arima_order_p, arima_order_d, arima_order_q),
        confidence_level=confidence_level,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
        plot_title=plot_title,
    )

    return result, Image(data=image_bytes) if image_bytes else None


@app.tool()
def forest_forecast(source_id: str, n: int = 4) -> Any:
    """随机森林预测"""
    df = read_source(source_id)
    return forest_try(n, df)


@app.tool()
def xgb_forecast(source_id: str, column_index: int = 16) -> Any:
    """XGBoost 预测"""
    df = read_source(source_id)
    return xgboost_forecast(column_index, df)


@app.tool()
def bp_forecast(source_id: str, column_index: int = 16) -> Any:
    """BP 神经网络预测 (需要 TensorFlow)"""
    df = read_source(source_id)
    return zero_and_bp_predict(column_index, df)


if __name__ == "__main__":  # pragma: no cover
    app.run("sse")
