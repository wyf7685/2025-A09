"""
指数平滑预测模块

提供一次、二次和三次指数平滑预测方法的标准化实现。
包括参数优化、预测评估和可视化功能。
"""

import io
import time
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

from ..log import logger
from .analysis_results import EMAAnalysisResult


def ema_forecast_impl(
    df: pd.DataFrame,
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
) -> tuple[EMAAnalysisResult, bytes | None]:
    """
    指数平滑预测实现函数，包括一次、二次和三次指数平滑

    Args:
        df: 输入数据框
        target_column: 目标预测列名
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
        tuple: (EMAAnalysisResult, bytes | None)
            - EMAAnalysisResult: 预测分析结果对象
            - bytes: PNG格式的图像数据(如果启用诊断)
    """
    start_time = time.time()
    warnings_list = []

    # 默认参数设置
    if smoothing_methods is None:
        smoothing_methods = ["single", "double", "triple"]
    if alphas is None:
        alphas = cast("list[float]", list(np.arange(0.10, 1.0, 0.10)))
    if betas is None:
        betas = cast("list[float]", list(np.arange(0.10, 1.0, 0.10)))
    if gammas is None:
        gammas = cast("list[float]", list(np.arange(0.10, 1.0, 0.10)))
    if season_periods is None:
        season_periods = list(range(2, 7))

    try:
        # 数据验证
        if target_column not in df.columns:
            raise ValueError(f"目标列 '{target_column}' 不存在")
        if time_column not in df.columns:
            raise ValueError(f"时间列 '{time_column}' 不存在")

        # 提取相关列并保存原始列名用于展示
        df_work = df[[time_column, target_column]].copy()

        # 设置时间索引
        df_work = df_work.set_index(time_column)

        # 划分训练和测试集
        split_idx = int((1 - test_size) * len(df_work))
        train = df_work.iloc[:split_idx]
        test = df_work.iloc[split_idx:]
        train_series = train[target_column].astype(float)
        test_series = test[target_column].astype(float)

        # 记录训练和测试集的日期范围
        train_start_date = str(train.index[0])
        train_end_date = str(train.index[-1])
        test_start_date = str(test.index[0])
        test_end_date = str(test.index[-1])

        # 指数平滑优化器函数

        # 一次指数平滑优化器
        def ses_optimizer(
            train_data: pd.Series, alpha_values: list[float], steps: int
        ) -> tuple[float, float, pd.Series]:
            best_alpha = 0.1
            best_mape = float("inf")
            best_forecast = None

            for alpha in alpha_values:
                ses_model = SimpleExpSmoothing(train_data).fit(smoothing_level=alpha)
                forecast = ses_model.forecast(steps)
                mape = np.mean(np.abs((forecast.to_numpy() - test_series.to_numpy()) / test_series.to_numpy()))

                if mape < best_mape:
                    best_alpha = alpha
                    best_mape = mape
                    best_forecast = forecast

            if best_forecast is None:
                raise ValueError("一次指数平滑未能找到有效的预测结果")

            logger.info(f"一次指数平滑最佳alpha: {best_alpha:.2f}, MAPE: {best_mape:.4f}")
            return best_alpha, best_mape, best_forecast

        # 二次指数平滑优化器
        def des_optimizer(
            train_data: pd.Series, alpha_values: list[float], beta_values: list[float], steps: int
        ) -> tuple[float, float, float, pd.Series]:
            best_alpha = 0.1
            best_beta = 0.1
            best_mape = float("inf")
            best_forecast = None

            for alpha in alpha_values:
                for beta in beta_values:
                    des_model = ExponentialSmoothing(train_data, trend="add").fit(
                        smoothing_level=alpha, smoothing_trend=beta
                    )
                    forecast = des_model.forecast(steps)
                    mape = np.mean(np.abs((forecast.to_numpy() - test_series.to_numpy()) / test_series.to_numpy()))

                    if mape < best_mape:
                        best_alpha = alpha
                        best_beta = beta
                        best_mape = mape
                        best_forecast = forecast

            if best_forecast is None:
                raise ValueError("二次指数平滑未能找到有效的预测结果")

            logger.info(f"二次指数平滑最佳参数: alpha={best_alpha:.2f}, beta={best_beta:.2f}, MAPE: {best_mape:.4f}")
            return best_alpha, best_beta, best_mape, best_forecast

        # 三次指数平滑优化器
        def tes_optimizer(
            train_data: pd.Series,
            alpha_values: list[float],
            beta_values: list[float],
            gamma_values: list[float],
            season_period_values: list[int],
            steps: int,
        ) -> tuple[float, float, float, int, float, pd.Series]:
            best_alpha = 0.1
            best_beta = 0.1
            best_gamma = 0.1
            best_season_period = 4
            best_mape = float("inf")
            best_forecast = None

            for alpha in alpha_values:
                for beta in beta_values:
                    for gamma in gamma_values:
                        for season_period in season_period_values:
                            try:
                                tes_model = ExponentialSmoothing(
                                    train_data, trend="add", seasonal="add", seasonal_periods=season_period
                                ).fit(smoothing_level=alpha, smoothing_trend=beta, smoothing_seasonal=gamma)

                                forecast = tes_model.forecast(steps)
                                mape = np.mean(
                                    np.abs((forecast.to_numpy() - test_series.to_numpy()) / test_series.to_numpy())
                                )

                                if mape < best_mape:
                                    best_alpha = alpha
                                    best_beta = beta
                                    best_gamma = gamma
                                    best_season_period = season_period
                                    best_mape = mape
                                    best_forecast = forecast
                            except Exception as e:
                                warnings_list.append(f"三次指数平滑参数组合错误: {e}")
                                continue

            if best_forecast is None:
                raise ValueError("三次指数平滑未能找到有效的预测结果")

            logger.info(
                f"三次指数平滑最佳参数: alpha={best_alpha:.2f}, beta={best_beta:.2f}, "
                f"gamma={best_gamma:.2f}, season_period={best_season_period}, MAPE: {best_mape:.4f}"
            )
            return best_alpha, best_beta, best_gamma, best_season_period, best_mape, best_forecast

        # 根据选定的方法执行预测
        forecasts = {}
        test_steps = len(test)

        # 一次指数平滑
        best_alpha_one = best_mape_one = forecast_one = None
        if "single" in smoothing_methods:
            best_alpha_one, best_mape_one, forecast_one = ses_optimizer(train_series, alphas, test_steps)
            forecasts["single"] = forecast_one

        # 二次指数平滑
        best_alpha_two = best_beta_two = best_mape_two = forecast_two = None
        if "double" in smoothing_methods:
            best_alpha_two, best_beta_two, best_mape_two, forecast_two = des_optimizer(
                train_series, alphas, betas, test_steps
            )
            forecasts["double"] = forecast_two

        # 三次指数平滑
        best_alpha_three = best_beta_three = best_gamma_three = best_season_period = best_mape_three = (
            forecast_three
        ) = None
        if "triple" in smoothing_methods:
            best_alpha_three, best_beta_three, best_gamma_three, best_season_period, best_mape_three, forecast_three = (
                tes_optimizer(train_series, alphas, betas, gammas, season_periods, test_steps)
            )
            forecasts["triple"] = forecast_three

        # 选择最佳预测模型
        best_method = None
        best_mape = float("inf")
        best_forecast = None

        for method, forecast in forecasts.items():
            if method == "single" and best_mape_one is not None and best_mape_one < best_mape:
                best_method = method
                best_mape = best_mape_one
                best_forecast = forecast
            elif method == "double" and best_mape_two is not None and best_mape_two < best_mape:
                best_method = method
                best_mape = best_mape_two
                best_forecast = forecast
            elif method == "triple" and best_mape_three is not None and best_mape_three < best_mape:
                best_method = method
                best_mape = best_mape_three
                best_forecast = forecast

        logger.info(f"最佳预测方法: {best_method}, MAPE: {best_mape:.4f}")

        # 计算其他评估指标
        if best_forecast is not None:
            mae = np.mean(np.abs(best_forecast.to_numpy() - test_series.to_numpy()))
            mse = np.mean((best_forecast.to_numpy() - test_series.to_numpy()) ** 2)
            rmse = np.sqrt(mse)

            # 计算R-squared
            ss_res = np.sum((test_series.to_numpy() - best_forecast.to_numpy()) ** 2)
            ss_tot = np.sum((test_series.to_numpy() - np.mean(test_series.to_numpy())) ** 2)
            r_squared = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0
        else:
            mae = mse = rmse = r_squared = 0.0
            warnings_list.append("未找到有效的预测结果")

        # 创建图表
        image_bytes = None
        if enable_diagnostics and best_forecast is not None:
            plt.figure(figsize=(12, 8))

            # 创建子图
            _, axes = plt.subplots(2, 1, figsize=(12, 10))

            # 上图: 原始数据和所有预测
            axes[0].plot(df_work.index, df_work[target_column], label="原始数据", color="black")

            if "single" in forecasts and forecast_one is not None:
                axes[0].plot(
                    test.index,
                    forecast_one,
                    label=f"一次指数平滑 (α={best_alpha_one:.2f}, MAPE={best_mape_one:.2%})",
                    color="blue",
                )

            if "double" in forecasts and forecast_two is not None:
                axes[0].plot(
                    test.index,
                    forecast_two,
                    label=f"二次指数平滑 (α={best_alpha_two:.2f}, β={best_beta_two:.2f}, MAPE={best_mape_two:.2%})",
                    color="green",
                )

            if "triple" in forecasts and forecast_three is not None:
                axes[0].plot(
                    test.index,
                    forecast_three,
                    label=(
                        f"三次指数平滑 "
                        f"(α={best_alpha_three:.2f},"
                        f" β={best_beta_three:.2f},"
                        f" γ={best_gamma_three:.2f},"
                        f" MAPE={best_mape_three:.2%})"
                    ),
                    color="red",
                )

            axes[0].set_title(f"{column_label or target_column} - 各指数平滑方法对比")
            axes[0].set_xlabel("日期")
            axes[0].set_ylabel("值")
            axes[0].legend()
            axes[0].grid(visible=True, linestyle="--", linewidth=0.5)

            # 下图: 残差分析
            if best_forecast is not None:
                residuals = test_series.to_numpy() - best_forecast.to_numpy()
                axes[1].scatter(test.index, residuals, color="purple", alpha=0.6)
                axes[1].axhline(y=0, color="r", linestyle="-")
                axes[1].set_title(f"最佳模型({best_method})残差分析")
                axes[1].set_xlabel("日期")
                axes[1].set_ylabel("残差")
                axes[1].grid(visible=True, linestyle="--", linewidth=0.5)

            plt.tight_layout()

            # 保存图表
            with io.BytesIO() as buf:
                plt.savefig(buf, format="png")
                buf.seek(0)
                image_bytes = buf.getvalue()

            plt.close()

        # 创建结果对象
        result = EMAAnalysisResult(
            # 基本信息
            algorithm_name="ExponentialSmoothing",
            target_column=target_column,
            # 数据信息
            total_samples=len(df_work),
            train_samples=len(train),
            test_samples=len(test),
            train_start_date=train_start_date,
            train_end_date=train_end_date,
            test_start_date=test_start_date,
            test_end_date=test_end_date,
            # 最佳模型的评估指标
            mape=best_mape * 100,  # 转换为百分比
            mae=mae,
            mse=mse,
            rmse=rmse,
            r_squared=r_squared,
            # 一次指数平滑参数和结果
            alpha=best_alpha_one or 0.0,
            mape_one=best_mape_one * 100 if best_mape_one else 0.0,  # 转换为百分比
            # 二次指数平滑参数和结果
            beta=best_beta_two or 0.0,
            mape_two=best_mape_two * 100 if best_mape_two else 0.0,  # 转换为百分比
            # 三次指数平滑参数和结果
            gamma=best_gamma_three or 0.0,
            season_periods=best_season_period or 0,
            mape_three=best_mape_three * 100 if best_mape_three else 0.0,  # 转换为百分比
            # 季节性信息
            has_seasonality=best_method == "triple",
            # 预测数据
            actual_values=test_series.to_numpy().tolist(),
            predicted_values=best_forecast.to_numpy().tolist() if best_forecast is not None else [],
            # 诊断信息
            warnings=warnings_list,
            execution_time=time.time() - start_time,
        )

        logger.info(f"EMA分析完成，执行时间: {result.execution_time:.2f}秒")
        return result, image_bytes

    except Exception as e:
        logger.exception("EMA分析失败")
        raise RuntimeError(f"EMA分析失败: {e!r}") from e
