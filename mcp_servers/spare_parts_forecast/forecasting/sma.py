"""
简单移动平均法(SMA)预测模块

提供简单移动平均和加权移动平均的时间序列预测功能。
包括数据预处理、参数优化、预测和结果可视化等功能。
"""

import io
import logging
import time
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .analysis_results import SMAAnalysisResult

logger = logging.getLogger(__name__)


def sma_forecast_impl(
    df: pd.DataFrame,
    target_column: str,
    time_column: str = "time",
    window_size: int = 3,
    test_size: float = 0.2,
    optimize_weights: bool = True,
    weight_combinations: list[list[float]] | None = None,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
    plot_title: str | None = None,
) -> tuple[SMAAnalysisResult, bytes | None]:
    """
    简单移动平均预测实现函数

    Args:
        df: 输入数据框
        target_column: 目标预测列名
        time_column: 时间列名，默认为"time"
        window_size: 移动平均窗口大小，默认为3
        test_size: 测试集比例，默认为0.2
        optimize_weights: 是否优化权重，默认为True
        weight_combinations: 自定义权重组合列表，默认为None(使用预设组合)
        enable_diagnostics: 是否启用诊断，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值
        plot_title: 图表标题，默认为None(自动生成)

    Returns:
        tuple: (SMAAnalysisResult, bytes | None)
            - SMAAnalysisResult: 预测分析结果对象
            - bytes: PNG格式的图像数据(如果启用诊断)
    """
    start_time = time.time()
    warnings_list = []

    # 参数验证
    if window_size < 2:
        warnings_list.append(f"窗口大小({window_size})太小，已调整为2")
        window_size = 2

    # 准备默认的权重组合
    if weight_combinations is None:
        weight_combinations = [
            [0.1, 0.3, 0.6],  # 偏向最近数据
            [0.2, 0.3, 0.5],  # 稍微平衡
            [0.2, 0.4, 0.4],  # 中间偏重
            [0.3, 0.3, 0.4],  # 均衡分布
            [0.1, 0.4, 0.5],  # 中间偏重
            [0.1, 0.2, 0.7],  # 严重偏向最近数据
        ]

    # 确保所有权重组合的长度与窗口大小匹配
    valid_weight_combinations = []
    for weights in weight_combinations:
        if len(weights) == window_size:
            valid_weight_combinations.append(weights)
        else:
            warnings_list.append(f"权重{weights}长度与窗口大小{window_size}不匹配，已忽略")

    # 如果没有有效的权重组合，创建均匀权重
    if not valid_weight_combinations and optimize_weights:
        uniform_weight = 1.0 / window_size
        valid_weight_combinations = [[uniform_weight] * window_size]
        warnings_list.append("未找到有效的权重组合，已使用均匀权重")

    try:
        # 数据验证
        if target_column not in df.columns:
            raise ValueError(f"目标列 '{target_column}' 不存在")
        if time_column not in df.columns:
            raise ValueError(f"时间列 '{time_column}' 不存在")

        # 提取相关列并保存原始列名用于展示
        df_work = cast("pd.DataFrame", df[[time_column, target_column]]).copy()

        # 计算简单移动平均
        sma_values = cast("pd.DataFrame", df_work[target_column].rolling(window=window_size).mean())

        # 优化权重
        best_weights = None
        wma_values = None
        mape_wight = float("inf")
        mape_single = float("inf")

        if optimize_weights:
            for weights in valid_weight_combinations:
                # 计算当前权重的移动加权平均
                current_wma = (
                    df_work[target_column].rolling(window=window_size).apply(lambda x, w=weights: (x * w).sum())
                )

                # 计算MAPE (排除前window_size-1个NaN值)
                start_idx = window_size - 1
                y_values = current_wma[start_idx:-1].to_numpy()  # pyright: ignore[reportAttributeAccessIssue]
                actual_values = df_work[target_column][start_idx + 1 :].to_numpy()  # pyright: ignore[reportAttributeAccessIssue]

                # 避免除零错误
                actual_nonzero = np.where(actual_values != 0, actual_values, 1e-10)
                current_mape = np.mean(np.abs((y_values - actual_values) / actual_nonzero))

                # 更新最佳MAPE和权重
                if current_mape < mape_wight:
                    mape_wight = current_mape
                    best_weights = weights
                    wma_values = current_wma

            logger.info(f"最佳权重组合: {best_weights}")
            logger.info(f"最佳加权MAPE: {mape_wight}")

        # 计算简单移动平均的MAPE
        start_idx = window_size - 1
        sma_y_values = sma_values[start_idx:-1].to_numpy()  # pyright: ignore[reportAttributeAccessIssue]
        actual_values = df_work[target_column][start_idx + 1 :].to_numpy()  # pyright: ignore[reportAttributeAccessIssue]

        # 避免除零错误
        actual_nonzero = np.where(actual_values != 0, actual_values, 1e-10)
        mape_single = np.mean(np.abs((sma_y_values - actual_values) / actual_nonzero))

        # 计算其他指标
        mae_single = np.mean(np.abs(sma_y_values - actual_values))
        mse_single = np.mean((sma_y_values - actual_values) ** 2)
        rmse_single = np.sqrt(mse_single)

        # 计算R-squared
        ss_res = np.sum((actual_values - sma_y_values) ** 2)
        ss_tot = np.sum((actual_values - np.mean(actual_values)) ** 2)
        r_squared = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0

        # 准备测试数据用于可视化
        split_idx = int((1 - test_size) * len(df_work))
        train_data = df_work.iloc[:split_idx]
        test_data = df_work.iloc[split_idx:]

        # 创建图表
        image_bytes = None
        if enable_diagnostics:
            # 生成图表
            title = plot_title or f"{column_label or target_column} - 移动平均预测分析"
            plt.figure(figsize=(10, 6))
            plt.plot(df_work[time_column], df_work[target_column], label="原始数据", color="black")
            plt.plot(
                df_work[time_column].iloc[window_size - 1 :],
                sma_values.iloc[window_size - 1 :],
                label=f"简单移动平均 (窗口={window_size})",
                color="blue",
            )

            if optimize_weights and wma_values is not None:
                plt.plot(
                    df_work[time_column].iloc[window_size - 1 :],
                    wma_values.iloc[window_size - 1 :],
                    label=f"加权移动平均 (权重={best_weights})",
                    color="red",
                )

            plt.xlabel("日期")
            plt.ylabel("数值")
            plt.title(title)
            plt.legend()
            plt.xticks(rotation=45)
            plt.grid(visible=True, linestyle="--", linewidth=0.5)
            plt.tight_layout()

            with io.BytesIO() as buf:
                plt.savefig(buf, format="png")
                buf.seek(0)
                image_bytes = buf.getvalue()
            plt.close()

        # 创建结果对象
        result = SMAAnalysisResult(
            # 基本信息
            algorithm_name="SimpleMovingAverage",
            target_column=target_column,
            # 数据信息
            total_samples=len(df_work),
            train_samples=len(train_data),
            test_samples=len(test_data),
            train_start_date=str(train_data[time_column].iloc[0]),
            train_end_date=str(train_data[time_column].iloc[-1]),
            test_start_date=str(test_data[time_column].iloc[0]),
            test_end_date=str(test_data[time_column].iloc[-1]),
            # 预测评估指标
            mape=float(mape_single * 100),  # 转换为百分比
            mae=float(mae_single),
            mse=float(mse_single),
            rmse=rmse_single,
            r_squared=r_squared,
            # SMA特定参数
            window_size=window_size,
            mape_single=float(mape_single * 100),  # 转换为百分比
            mape_weighted=float(mape_wight * 100) if optimize_weights else 0.0,  # 转换为百分比
            best_weights=best_weights if optimize_weights and best_weights is not None else [],
            # 预测数据
            actual_values=actual_values.tolist(),
            predicted_values=sma_y_values.tolist(),
            # 诊断信息
            warnings=warnings_list,
            execution_time=time.time() - start_time,
        )

        logger.info(f"SMA分析完成，执行时间: {result.execution_time:.2f}秒")
        return result, image_bytes

    except Exception as e:
        logger.exception("SMA分析失败")
        raise RuntimeError(f"SMA分析失败: {e!r}") from e
