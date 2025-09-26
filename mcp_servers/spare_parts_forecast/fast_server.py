"""FastMCP based server for spare parts forecasting.

Run (package mode):
    python -m mcp_servers.spare_parts_forecast.fast_server
"""

import logging
from typing import Any, Literal

import pandas as pd
from mcp.server import FastMCP
from mcp.server.fastmcp import Image

from .data_source import read_agent_source_data
from .forecasting import (
    ARIMAAnalysisResult,
    CrostonAnalysisResult,
    EMAAnalysisResult,
    SMAAnalysisResult,
    arima_forecast_impl,
    croston_forecast_impl,
    ema_forecast_impl,
    forest_try,
    get_available_algorithms,
    list_algorithms,
    sma_forecast_impl,
    xgboost_forecast,
    zero_and_bp_predict,
)

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
"""

app = FastMCP(
    name="spare-parts-forecast-fast",
    instructions=instructions,
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
def sma_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    window_size: int = 3,
    optimize_weights: bool = True,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
    plot_title: str | None = None,
) -> tuple[SMAAnalysisResult, Any | None]:
    """
    SMA简单移动平均时间序列预测分析

    执行简单移动平均模型预测，提供详细的统计分析和诊断信息。
    支持优化加权移动平均并与标准SMA进行比较，展示详细的预测评估指标。

    Args:
        source_id: 数据源ID，用于获取预测数据
        target_column: 目标预测列名，指定要预测的数据列
        time_column: 时间列名，默认为"time"
        window_size: 移动平均窗口大小，默认为3
        optimize_weights: 是否自动优化权重组合，默认为True
        enable_diagnostics: 是否启用详细诊断分析和图表生成，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值
        plot_title: 图表标题，默认为None(自动生成)

    Returns:
        SMAAnalysisResult | tuple[SMAAnalysisResult, Image]: 包含以下键值的分析结果字典:
            - target_column: 预测目标列名
            - window_size: 移动平均窗口大小
            - total_samples: 总样本数
            - train_samples: 训练样本数
            - test_samples: 测试样本数
            - mape: 平均绝对百分比误差(%)
            - mae: 平均绝对误差
            - rmse: 均方根误差
            - r_squared: 决定系数
            - mape_weighted: 加权移动平均的MAPE(%)
            - best_weights: 最佳权重组合(如果启用权重优化)
            - actual_values: 实际观测值列表
            - predicted_values: 预测值列表
            - execution_time: 执行时间(秒)
            - warnings: 警告信息列表
            启用诊断模式时，还会返回图表

    Raises:
        ValueError: 当指定的列不存在或数据格式错误时
        RuntimeError: 当预测过程出错时

    Example:
        基础预测:
        ```
        result = sma_forecast("data_001", "demand_quantity")
        print(f"预测MAPE: {result.mape:.2f}%")
        ```

        自定义参数预测:
        ```
        result = sma_forecast(
            source_id="data_001",
            target_column="sales_volume",
            time_column="date",
            window_size=4,
            optimize_weights=True,
            plot_title="销量移动平均预测分析"
        )
        ```

    Note:
        - 简单移动平均适用于短期平稳或低波动性的时间序列数据
        - 窗口大小决定了模型对历史数据的敏感度，较大窗口平滑效果更强
        - 启用权重优化可以提高预测准确性，特别是对于趋势型数据
        - 对于季节性或非线性趋势数据，可能不如其他预测方法准确
    """
    df = read_source(source_id)

    # 调用SMA预测函数
    result, image_bytes = sma_forecast_impl(
        df=df,
        target_column=target_column,
        time_column=time_column,
        window_size=window_size,
        optimize_weights=optimize_weights,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
        plot_title=plot_title,
    )

    return result, Image(data=image_bytes) if image_bytes else None


@app.tool()
def ema_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    smoothing_methods: list[str] | None = None,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
) -> tuple[EMAAnalysisResult, Any | None]:
    """
    EMA指数平滑时间序列预测分析

    执行指数平滑预测，包括一次、二次和三次指数平滑，并自动选择最佳模型。
    提供详细的统计分析和诊断信息，支持可视化对比不同平滑方法的性能。

    Args:
        source_id: 数据源ID，用于获取预测数据
        target_column: 目标预测列名，指定要预测的数据列
        time_column: 时间列名，默认为"time"
        smoothing_methods: 要使用的平滑方法列表，可选值为"single", "double", "triple"，默认使用所有方法
        enable_diagnostics: 是否启用详细诊断分析和图表生成，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值

    Returns:
        EMAAnalysisResult | tuple[EMAAnalysisResult, Image]: 包含以下键值的分析结果:
            - target_column: 预测目标列名
            - total_samples: 总样本数
            - train_samples: 训练样本数
            - test_samples: 测试样本数
            - mape: 平均绝对百分比误差(%)
            - mae: 平均绝对误差
            - rmse: 均方根误差
            - r_squared: 决定系数
            - alpha: 一次指数平滑最佳alpha参数
            - mape_one: 一次指数平滑MAPE(%)
            - beta: 二次指数平滑最佳beta参数
            - mape_two: 二次指数平滑MAPE(%)
            - gamma: 三次指数平滑最佳gamma参数
            - season_periods: 季节性周期
            - mape_three: 三次指数平滑MAPE(%)
            - has_seasonality: 是否存在季节性
            - actual_values: 实际观测值列表
            - predicted_values: 预测值列表
            - execution_time: 执行时间(秒)
            - warnings: 警告信息列表
            启用诊断模式时，还会返回图表

    Raises:
        ValueError: 当指定的列不存在或数据格式错误时
        RuntimeError: 当预测过程出错时

    Example:
        基础预测:
        ```
        result = ema_forecast("data_001", "demand_quantity")
        print(f"预测MAPE: {result.mape:.2f}%")
        ```

        选择特定平滑方法:
        ```
        result = ema_forecast(
            source_id="data_001",
            target_column="sales_volume",
            time_column="date",
            smoothing_methods=["single", "triple"],
        )
        ```

    Note:
        - 一次指数平滑适用于无明显趋势和季节性的数据
        - 二次指数平滑适用于有趋势但无季节性的数据
        - 三次指数平滑适用于同时具有趋势和季节性的数据
        - 系统会自动优化各模型参数并选择最佳模型
    """
    df = read_source(source_id)

    if smoothing_methods is None:
        smoothing_methods = ["single", "double", "triple"]

    # 调用EMA预测函数
    result, image_bytes = ema_forecast_impl(
        df=df,
        target_column=target_column,
        time_column=time_column,
        smoothing_methods=smoothing_methods,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
    )

    return result, Image(data=image_bytes) if image_bytes else None


@app.tool()
def croston_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    methods: list[Literal["croston", "sba", "tsb"]] | None = None,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
) -> tuple[CrostonAnalysisResult, Any | None]:
    """
    Croston间歇性需求预测分析

    执行Croston方法及其变体(SBA, TSB)用于间歇性需求预测，
    专为处理含有大量零需求的时间序列数据而设计。
    提供详细的统计分析和诊断信息。

    Args:
        source_id: 数据源ID，用于获取预测数据
        target_column: 目标预测列名，指定要预测的数据列
        time_column: 时间列名，默认为"time"
        methods: 要使用的方法列表，可选值为"croston", "sba", "tsb"，默认使用所有方法
        enable_diagnostics: 是否启用详细诊断分析和图表生成，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值

    Returns:
        CrostonAnalysisResult | tuple[CrostonAnalysisResult, Image]: 包含以下键值的分析结果:
            - target_column: 预测目标列名
            - total_samples: 总样本数
            - train_samples: 训练样本数
            - test_samples: 测试样本数
            - mape: 平均绝对百分比误差(%)
            - mae: 平均绝对误差
            - rmse: 均方根误差
            - r_squared: 决定系数
            - alpha_cst: 标准Croston方法的alpha参数
            - mape_cst: 标准Croston方法的MAPE(%)
            - alpha_sba: SBA变体的alpha参数
            - mape_sba: SBA变体的MAPE(%)
            - alpha_tsb: TSB变体的alpha参数
            - beta_tsb: TSB变体的beta参数
            - mape_tsb: TSB变体的MAPE(%)
            - zero_percentage: 数据中零值的百分比
            - best_method: 最佳预测方法
            - actual_values: 实际观测值列表
            - predicted_values: 预测值列表
            - execution_time: 执行时间(秒)
            - warnings: 警告信息列表
            启用诊断模式时，还会返回图表

    Raises:
        ValueError: 当指定的列不存在或数据格式错误时
        RuntimeError: 当预测过程出错时

    Example:
        基础预测:
        ```
        result = croston_forecast("data_001", "demand_quantity")
        print(f"预测MAPE: {result.mape:.2f}%")
        print(f"最佳方法: {result.best_method}")
        ```

        选择特定方法:
        ```
        result = croston_forecast(
            source_id="data_001",
            target_column="sales_volume",
            time_column="date",
            methods=["croston", "sba"],
        )
        ```

    Note:
        - Croston方法特别适用于间歇性需求模式(有大量零值的时间序列)
        - 标准Croston方法通常对预测值有上偏差
        - SBA(Syntetos-Boylan近似)变体通常可以减少偏差
        - TSB(Teunter-Syntetos-Babai)方法可能在某些情况下表现更好
        - 系统会自动选择表现最佳的方法作为最终预测
    """
    df = read_source(source_id)

    # 调用Croston预测函数
    result, image_bytes = croston_forecast_impl(
        df=df,
        target_column=target_column,
        time_column=time_column,
        methods=methods,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
    )

    return result, Image(data=image_bytes) if image_bytes else None


@app.tool()
def arima_forecast(
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
) -> tuple[ARIMAAnalysisResult, Any | None]:
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


if __name__ == "__main__":
    app.run("sse")
