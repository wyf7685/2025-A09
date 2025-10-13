"""FastMCP based server for spare parts forecasting.

Run (package mode):
    python -m mcp_servers.spare_parts_forecast.fast_server
"""

import functools
from collections.abc import Callable
from typing import Any, Literal

from .log import LOGGING_CONFIG, configure_logging

configure_logging()

import anyio.to_thread
import pandas as pd
from mcp.server import FastMCP
from mcp.server.fastmcp import Image

from .data_source import read_agent_source_data
from .forecasting import (
    ARIMAAnalysisResult,
    BPNNAnalysisResult,
    CrostonAnalysisResult,
    EMAAnalysisResult,
    RandomForestAnalysisResult,
    SMAAnalysisResult,
    XGBoostAnalysisResult,
    arima_forecast_impl,
    bp_forecast_impl,
    croston_forecast_impl,
    ema_forecast_impl,
    forest_forecast_impl,
    get_available_algorithms,
    list_algorithms,
    sma_forecast_impl,
    xgboost_forecast_impl,
)

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


async def read_source(source_id: str) -> pd.DataFrame:
    # See app/core/agent/agents/data_analyzer/context.py
    ctx = app.get_context()
    params = ctx.request_context.session.client_params
    client_name = params and params.clientInfo.name
    assert client_name is not None, "Session ID is required"

    return await read_agent_source_data(client_name, source_id)


def wrap_image(image: bytes | None) -> Image | None:
    return Image(data=image) if image else None


async def run_sync[**P, R](_fn_: Callable[P, R], /, *args: P.args, **kwargs: P.kwargs) -> R:
    fn = functools.partial(_fn_, *args, **kwargs)
    return await anyio.to_thread.run_sync(fn, abandon_on_cancel=True)


@app.tool()
def algorithms() -> list[str]:
    """
    列出所有可用的预测算法

    Returns:
        list: 可用算法名称列表
    """
    return list_algorithms()


@app.tool()
def algorithm_categories() -> dict[str, list[str]]:
    """
    获取当前可用的预测算法列表

    Returns:
        dict: 按类别分组的可用算法字典
    """
    return get_available_algorithms()


@app.tool()
async def sma_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    window_size: int = 3,
    test_size: float = 0.2,
    optimize_weights: bool = True,
    weight_combinations: list[list[float]] | None = None,
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
        time_column: 时间列名，默认为"time"，该列值类型应为datetime
        window_size: 移动平均窗口大小，默认为3
        test_size: 测试集比例，取值范围0-1，默认为0.2(20%测试集)
        optimize_weights: 是否自动优化权重组合，默认为True
        weight_combinations: 自定义权重组合列表，默认为None(使用预设组合)
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
    df = await read_source(source_id)

    # 调用SMA预测函数
    result, image = await run_sync(
        sma_forecast_impl,
        df=df,
        target_column=target_column,
        time_column=time_column,
        window_size=window_size,
        test_size=test_size,
        optimize_weights=optimize_weights,
        weight_combinations=weight_combinations,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
        plot_title=plot_title,
    )

    return result, wrap_image(image)


@app.tool()
async def ema_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    test_size: float = 0.2,
    smoothing_methods: list[str] | None = None,
    alphas: list[float] | None = None,
    betas: list[float] | None = None,
    gammas: list[float] | None = None,
    season_periods: list[int] | None = None,
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
        test_size: 测试集比例，默认为0.2
        smoothing_methods: 要使用的平滑方法列表，可选值为"single", "double", "triple"
        alphas: alpha参数候选值列表，默认为0.1到0.9，步长0.1
        betas: beta参数候选值列表，默认为0.1到0.9，步长0.1
        gammas: gamma参数候选值列表，默认为0.1到0.9，步长0.1
        season_periods: 季节性周期候选值列表，默认为2到6
        enable_diagnostics: 是否启用诊断，默认为True
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
    df = await read_source(source_id)

    if smoothing_methods is None:
        smoothing_methods = ["single", "double", "triple"]

    # 调用EMA预测函数
    result, image = await run_sync(
        ema_forecast_impl,
        df=df,
        target_column=target_column,
        time_column=time_column,
        test_size=test_size,
        smoothing_methods=smoothing_methods,
        alphas=alphas,
        betas=betas,
        gammas=gammas,
        season_periods=season_periods,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
    )

    return result, wrap_image(image)


@app.tool()
async def croston_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    test_size: float = 0.2,
    methods: list[Literal["croston", "sba", "tsb"]] | None = None,
    alpha_range: list[float] | None = None,
    beta_range: list[float] | None = None,
    extra_periods: int = 0,
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
        test_size: 测试集比例，默认为0.2
        methods: 要使用的方法列表，可选值为"croston", "sba", "tsb"
        alpha_range: alpha参数候选值列表，默认为0.1到0.9，步长0.1
        beta_range: beta参数候选值列表(TSB方法)，默认为0.1到0.9，步长0.1
        extra_periods: 额外预测的期数，默认为0
        enable_diagnostics: 是否启用诊断，默认为True
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
    df = await read_source(source_id)

    # 调用Croston预测函数
    result, image = await run_sync(
        croston_forecast_impl,
        df=df,
        target_column=target_column,
        time_column=time_column,
        test_size=test_size,
        methods=methods,
        alpha_range=alpha_range,
        beta_range=beta_range,
        extra_periods=extra_periods,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
    )

    return result, wrap_image(image)


@app.tool()
async def arima_forecast(
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
        time_column: 时间列名，默认为"time"，该列值类型应为datetime
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
    df = await read_source(source_id)

    # 调用ARIMA预测函数
    result, image = await run_sync(
        arima_forecast_impl,
        df=df,
        target_column=target_column,
        time_column=time_column,
        arima_order=(arima_order_p, arima_order_d, arima_order_q),
        confidence_level=confidence_level,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
        plot_title=plot_title,
    )

    return result, wrap_image(image)


@app.tool()
async def forest_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    feature_columns: list[str] | None = None,
    test_size: float = 0.2,
    n_estimators_range: list[int] | None = None,
    max_depth_range: list[int] | None = None,
    random_state: int = 42,
    extra_periods: int = 0,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
    plot_title: str | None = None,
) -> tuple[RandomForestAnalysisResult, Any | None]:
    """
    随机森林时间序列预测分析

    执行随机森林模型预测，优化模型参数并提供详细的统计分析和诊断信息。
    自动执行特征工程，参数优化和模型评估。

    Args:
        source_id: 数据源ID，用于获取预测数据
        target_column: 目标预测列名，指定要预测的数据列
        time_column: 时间列名，默认为"time"，该列值类型应为datetime
        feature_columns: 特征列名列表，默认为None（自动生成时间特征）
        test_size: 测试集比例，默认为0.2
        n_estimators_range: 随机森林树数量范围，默认为[5, 10, ..., 95, 100]
        max_depth_range: 决策树最大深度范围，默认为[5, 10, ..., 95, 100]
        random_state: 随机种子，默认为42
        extra_periods: 额外预测的期数，默认为0
        enable_diagnostics: 是否启用诊断，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值
        plot_title: 图表标题，默认为None(自动生成)

    Returns:
        RandomForestAnalysisResult | tuple[RandomForestAnalysisResult, Image]: 包含以下分析结果:
            - target_column: 预测目标列名
            - total_samples: 总样本数
            - train_samples: 训练样本数
            - test_samples: 测试样本数
            - mape: 平均绝对百分比误差(%)
            - mae: 平均绝对误差
            - rmse: 均方根误差
            - r_squared: 决定系数
            - n_estimators: 最优树的数量
            - max_depth: 最优树的最大深度
            - feature_importances: 特征重要性字典
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
        result = forest_forecast("data_001", "demand_quantity")
        print(f"预测MAPE: {result.mape:.2f}%")
        print(f"最佳树数量: {result.n_estimators}")
        ```

        自定义参数预测:
        ```
        result = forest_forecast(
            source_id="data_001",
            target_column="sales_volume",
            time_column="date",
            n_estimators_range=[50, 100, 150],
            max_depth_range=[10, 20, 30],
            plot_title="销量随机森林预测分析"
        )
        ```

    Note:
        - 随机森林适合复杂非线性数据，不受线性关系限制
        - 自动特征工程可处理时间列的年、季度、月信息
        - 参数优化可以找到最佳的模型配置
        - 如需自定义特征，可通过feature_columns参数指定
        - 模型会计算特征重要性，帮助理解影响因素
    """
    df = await read_source(source_id)

    # 调用随机森林预测函数
    result, image = await run_sync(
        forest_forecast_impl,
        df=df,
        target_column=target_column,
        time_column=time_column,
        feature_columns=feature_columns,
        test_size=test_size,
        n_estimators_range=n_estimators_range,
        max_depth_range=max_depth_range,
        random_state=random_state,
        extra_periods=extra_periods,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
        plot_title=plot_title,
    )

    return result, wrap_image(image)


@app.tool()
async def xgb_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    feature_columns: list[str] | None = None,
    test_size: float = 0.2,
    learning_rate_range: list[float] | None = None,
    max_depth_range: list[int] | None = None,
    n_estimators_range: list[int] | None = None,
    gwo_agents: int = 10,
    gwo_iterations: int = 2,
    random_state: int = 42,
    extra_periods: int = 0,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
    plot_title: str | None = None,
) -> tuple[XGBoostAnalysisResult, Any | None]:
    """
    XGBoost时间序列预测分析（基于灰狼优化）

    执行基于XGBoost的时间序列预测，并使用灰狼优化算法自动调整超参数。
    提供详细的统计分析、特征重要性和诊断信息。

    Args:
        source_id: 数据源ID，用于获取预测数据
        target_column: 目标预测列名，指定要预测的数据列
        time_column: 时间列名，默认为"time"，该列值类型应为datetime
        feature_columns: 特征列名列表，默认为None（自动生成时间特征）
        test_size: 测试集比例，默认为0.2
        learning_rate_range: 学习率范围，默认为[0.01, 0.05, 0.1, 0.2]
        max_depth_range: 最大深度范围，默认为[3, 5, 7, 9]
        n_estimators_range: 估计器数量范围，默认为[50, 100, 200, 300]
        gwo_agents: 灰狼优化算法搜索代理数量，默认为10
        gwo_iterations: 灰狼优化算法最大迭代次数，默认为2
        random_state: 随机种子，默认为42
        extra_periods: 额外预测的期数，默认为0
        enable_diagnostics: 是否启用详细诊断分析和图表生成，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值
        plot_title: 图表标题，默认为None(自动生成)

    Returns:
        XGBoostAnalysisResult | tuple[XGBoostAnalysisResult, Image]: 包含以下键值的分析结果:
            - target_column: 预测目标列名
            - total_samples: 总样本数
            - train_samples: 训练样本数
            - test_samples: 测试样本数
            - mape: 平均绝对百分比误差(%)
            - mae: 平均绝对误差
            - rmse: 均方根误差
            - r_squared: 决定系数
            - learning_rate: 最优学习率
            - max_depth: 最优最大深度
            - n_estimators: 最优估计器数量
            - feature_importances: 特征重要性字典
            - optimization_iterations: 优化迭代次数
            - optimization_scores: 各迭代分数列表
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
        result = xgb_forecast("data_001", "demand_quantity")
        print(f"预测MAPE: {result.mape:.2f}%")
        ```

        自定义参数优化:
        ```
        result = xgb_forecast(
            source_id="data_001",
            target_column="sales_volume",
            time_column="date",
            learning_rate_range=[0.01, 0.1, 0.5],
            max_depth_range=[3, 6, 9],
            n_estimators_range=[50, 150, 250],
            gwo_iterations=5,
            plot_title="销量XGBoost预测分析"
        )
        ```

    Note:
        - XGBoost结合灰狼优化算法能高效处理复杂非线性关系
        - 自动特征工程可处理时间列的年、季度、月等信息
        - 灰狼优化算法自动寻找最佳超参数组合
        - 可查看特征重要性，了解影响预测的关键因素
        - 增加gwo_iterations可提高参数优化质量，但会增加计算时间
    """
    df = await read_source(source_id)

    # 调用XGBoost预测函数
    result, image = await run_sync(
        xgboost_forecast_impl,
        df=df,
        target_column=target_column,
        time_column=time_column,
        feature_columns=feature_columns,
        test_size=test_size,
        learning_rate_range=learning_rate_range,
        max_depth_range=max_depth_range,
        n_estimators_range=n_estimators_range,
        gwo_agents=gwo_agents,
        gwo_iterations=gwo_iterations,
        random_state=random_state,
        extra_periods=extra_periods,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
        plot_title=plot_title,
    )

    return result, wrap_image(image)


@app.tool()
async def bp_forecast(
    source_id: str,
    target_column: str,
    time_column: str = "time",
    input_sizes: list[int] | None = None,
    hidden_sizes: list[int] | None = None,
    epochs: int = 100,
    batch_size: int = 16,
    learning_rate: float = 0.001,
    test_size: float = 0.2,
    random_state: int = 42,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
    plot_title: str | None = None,
) -> tuple[BPNNAnalysisResult, Any | None]:
    """
    BP神经网络时间序列预测分析

    执行基于BP神经网络的时间序列预测，支持自动调整输入和隐含层网络结构。
    提供详细的统计分析和诊断信息。需要安装TensorFlow库。

    Args:
        source_id: 数据源ID，用于获取预测数据
        target_column: 目标预测列名，指定要预测的数据列
        time_column: 时间列名，默认为"time"，该列值类型应为datetime
        input_sizes: 输入层尺寸范围，默认为[2,3,4,5,6]
        hidden_sizes: 隐含层尺寸范围，默认为[2,4,6,8,10,12]
        epochs: 训练轮数，默认为100
        batch_size: 批次大小，默认为16
        learning_rate: 学习率，默认为0.001
        test_size: 测试集比例，默认为0.2
        random_state: 随机种子，默认为42
        enable_diagnostics: 是否启用详细诊断分析和图表生成，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值
        plot_title: 图表标题，默认为None(自动生成)

    Returns:
        BPNNAnalysisResult | tuple[BPNNAnalysisResult, Image]: 包含以下键值的分析结果:
            - target_column: 预测目标列名
            - total_samples: 总样本数
            - train_samples: 训练样本数
            - test_samples: 测试样本数
            - mape: 平均绝对百分比误差(%)
            - mae: 平均绝对误差
            - rmse: 均方根误差
            - r_squared: 决定系数
            - input_size: 最优输入层大小
            - hidden_size: 最优隐含层大小
            - learning_rate: 使用的学习率
            - epochs: 训练轮数
            - batch_size: 批次大小
            - loss_history: 训练损失历史
            - val_loss_history: 验证损失历史
            - actual_values: 实际观测值列表
            - predicted_values: 预测值列表
            - execution_time: 执行时间(秒)
            - warnings: 警告信息列表

    Raises:
        ValueError: 当指定的列不存在或数据格式错误时
        RuntimeError: 当TensorFlow不可用或预测过程出错时

    Example:
        基础预测:
        ```
        result = bp_forecast("data_001", "demand_quantity")
        print(f"预测MAPE: {result.mape:.2f}%")
        ```

        自定义参数预测:
        ```
        result = bp_forecast(
            source_id="data_001",
            target_column="sales_volume",
            time_column="date",
            epochs=200,
            learning_rate=0.005,
            plot_title="销量BP神经网络预测分析"
        )
        ```

    Note:
        - BP神经网络适用于具有复杂非线性关系的时间序列数据
        - 模型需要足够的训练样本以避免过拟合
        - 此函数依赖TensorFlow库，若未安装将返回错误
        - 对于小样本或高噪声数据，可能需要调整学习率和网络结构
    """
    df = await read_source(source_id)

    # 调用BP神经网络预测函数
    result, image = await run_sync(
        bp_forecast_impl,
        df=df,
        target_column=target_column,
        time_column=time_column,
        input_sizes=input_sizes,
        hidden_sizes=hidden_sizes,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        test_size=test_size,
        random_state=random_state,
        enable_diagnostics=enable_diagnostics,
        column_label=column_label,
        plot_title=plot_title,
    )

    return result, wrap_image(image)


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
