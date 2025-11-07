"""
Croston方法及其变体用于间歇性需求预测

提供标准化的Croston方法、SBA和TSB变体实现，用于间歇性需求预测。
包括参数优化、预测评估和可视化功能。
"""

import io
import time
from typing import Literal, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..log import logger
from .analysis_results import CrostonAnalysisResult


def croston_forecast_impl(
    df: pd.DataFrame,
    target_column: str,
    time_column: str = "time",
    test_size: float = 0.2,
    methods: list[Literal["croston", "sba", "tsb"]] | None = None,
    alpha_range: list[float] | None = None,
    beta_range: list[float] | None = None,
    extra_periods: int = 0,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
) -> tuple[CrostonAnalysisResult, bytes | None]:
    """
    Croston方法及其变体预测实现函数，用于间歇性需求预测

    Args:
        df: 输入数据框
        target_column: 目标预测列名
        time_column: 时间列名，默认为"time"
        test_size: 测试集比例，默认为0.2
        methods: 要使用的方法列表，可选值为"croston", "sba", "tsb"
        alpha_range: alpha参数候选值列表，默认为0.1到0.9，步长0.1
        beta_range: beta参数候选值列表(TSB方法)，默认为0.1到0.9，步长0.1
        extra_periods: 额外预测的期数，默认为0
        enable_diagnostics: 是否启用诊断，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值

    Returns:
        tuple: (CrostonAnalysisResult, bytes | None)
            - CrostonAnalysisResult: 预测分析结果对象
            - bytes: PNG格式的图像数据(如果启用诊断)
    """
    start_time = time.time()
    warnings_list = []

    # 默认参数设置
    if methods is None:
        methods = ["croston", "sba", "tsb"]
    if alpha_range is None:
        alpha_range = cast("list[float]", list(np.arange(0.1, 1.0, 0.1)))
    if beta_range is None:
        beta_range = cast("list[float]", list(np.arange(0.1, 1.0, 0.1)))

    try:
        # 数据验证
        if target_column not in df.columns:
            raise ValueError(f"目标列 '{target_column}' 不存在")
        if time_column not in df.columns:
            raise ValueError(f"时间列 '{time_column}' 不存在")

        # 提取相关列并保存原始列名用于展示
        df_work = df[[time_column, target_column]].copy()

        # 划分训练和测试集
        split_idx = int((1 - test_size) * len(df_work))
        train = df_work.iloc[:split_idx]
        test = df_work.iloc[split_idx:]

        # 记录训练和测试集的日期范围
        train_start_date = str(train[time_column].iloc[0])
        train_end_date = str(train[time_column].iloc[-1])
        test_start_date = str(test[time_column].iloc[0])
        test_end_date = str(test[time_column].iloc[-1])

        # 使用整个数据集进行预测
        data_series = cast("pd.Series", df_work[target_column])

        # 检查数据是否适合Croston方法(至少有一个零值)
        if (data_series == 0).sum() == 0:
            warnings_list.append("数据中没有零值，可能不适合Croston方法")

        # 检查是否有过多的零值
        zero_percentage: float = (data_series == 0).mean() * 100
        if zero_percentage > 80:
            warnings_list.append(f"数据中有{zero_percentage:.1f}%的零值，可能导致预测不准确")

        # Croston方法实现
        def croston_method(ts: pd.Series, alpha: float, extra_periods: int = 1) -> pd.DataFrame:
            """标准Croston方法"""
            d = np.array(ts)
            cols = len(d)
            d = np.append(d, [np.nan] * extra_periods)

            # 初始化水平(a)、周期性(p)和预测(f)
            a, p, f = np.full((3, cols + extra_periods), np.nan)
            q = 1  # 自上次需求观察以来的期数

            # 初始化
            first_occurrence = np.argmax(d[:cols] > 0)
            a[0] = d[first_occurrence]
            p[0] = 1 + first_occurrence
            f[0] = a[0] / p[0]

            # 创建所有t+1时刻的预测
            for t in range(cols):
                if d[t] > 0:
                    a[t + 1] = alpha * d[t] + (1 - alpha) * a[t]
                    p[t + 1] = alpha * q + (1 - alpha) * p[t]
                    f[t + 1] = a[t + 1] / p[t + 1]
                    q = 1
                else:
                    a[t + 1] = a[t]
                    p[t + 1] = p[t]
                    f[t + 1] = f[t]
                    q += 1

            # 预测未来期间
            a[cols : cols + extra_periods] = a[cols - 1]
            p[cols : cols + extra_periods] = p[cols - 1]
            f[cols : cols + extra_periods] = f[cols - 1]

            return pd.DataFrame({"Demand": d, "Forecast": f, "Period": p, "Level": a, "Error": d - f})

        # SBA变体方法实现
        def sba_method(ts: pd.Series, alpha: float, extra_periods: int = 1) -> pd.DataFrame:
            """Syntetos-Boylan近似方法(SBA)"""
            d = np.array(ts)
            cols = len(d)
            d = np.append(d, [np.nan] * extra_periods)

            # 初始化水平(a)、周期性(p)和预测(f)
            a, p, f = np.full((3, cols + extra_periods), np.nan)
            q = 1  # 自上次需求观察以来的期数

            # 初始化
            first_occurrence = np.argmax(d[:cols] > 0)
            a[0] = d[first_occurrence]
            p[0] = 1 + first_occurrence
            f[0] = a[0] / p[0]

            # 创建所有t+1时刻的预测
            for t in range(cols):
                if d[t] > 0:
                    a[t + 1] = alpha * d[t] + (1 - alpha) * a[t]
                    p[t + 1] = alpha * q + (1 - alpha) * p[t]
                    f[t + 1] = (1 - alpha / 2) * (a[t + 1] / p[t + 1])
                    q = 1
                else:
                    a[t + 1] = a[t]
                    p[t + 1] = p[t]
                    f[t + 1] = f[t]
                    q += 1

            # 预测未来期间
            a[cols : cols + extra_periods] = a[cols - 1]
            p[cols : cols + extra_periods] = p[cols - 1]
            f[cols : cols + extra_periods] = f[cols - 1]

            return pd.DataFrame({"Demand": d, "Forecast": f, "Period": p, "Level": a, "Error": d - f})

        # TSB变体方法实现
        def tsb_method(ts: pd.Series, alpha: float, beta: float, extra_periods: int = 1) -> pd.DataFrame:
            """Teunter-Syntetos-Babai方法(TSB)"""
            d = np.array(ts)
            cols = len(d)
            d = np.append(d, [np.nan] * extra_periods)

            # 初始化水平(a)、概率(p)和预测(f)
            a, p, f = np.full((3, cols + extra_periods), np.nan)

            # 初始化
            first_occurrence = np.argmax(d[:cols] > 0)
            a[0] = d[first_occurrence]
            p[0] = 1 / (1 + first_occurrence)
            f[0] = p[0] * a[0]

            # 创建所有t+1时刻的预测
            for t in range(cols):
                if d[t] > 0:
                    a[t + 1] = alpha * d[t] + (1 - alpha) * a[t]
                    p[t + 1] = beta * 1 + (1 - beta) * p[t]
                else:
                    a[t + 1] = a[t]
                    p[t + 1] = (1 - beta) * p[t]
                f[t + 1] = p[t + 1] * a[t + 1]

            # 预测未来期间
            a[cols : cols + extra_periods] = a[cols - 1]
            p[cols : cols + extra_periods] = p[cols - 1]
            f[cols : cols + extra_periods] = f[cols - 1]

            return pd.DataFrame({"Demand": d, "Forecast": f, "Period": p, "Level": a, "Error": d - f})

        # 参数优化器函数

        # Croston原始方法优化器
        def cst_optimizer(data: pd.Series, alphas: list[float]) -> tuple[float, float, pd.DataFrame]:
            best_mape = float("inf")
            best_alpha = 0.1
            best_result = None

            for alpha in alphas:
                result = croston_method(data, float(alpha), extra_periods)
                forecast = result["Forecast"]

                # 避免除以零
                valid_idx = data != 0
                if valid_idx.sum() == 0:
                    continue

                mape = np.mean(
                    np.abs(
                        (
                            forecast[:-extra_periods].to_numpy()[valid_idx]  # pyright: ignore[reportAttributeAccessIssue]
                            - data.to_numpy()[valid_idx]
                        )
                        / data.to_numpy()[valid_idx]
                    )
                )

                if mape < best_mape:
                    best_alpha = float(alpha)
                    best_mape = float(mape)
                    best_result = result

                logger.debug(f"Croston alpha: {alpha:.2f}, MAPE: {mape:.4f}")

            if best_result is None:
                raise ValueError("无法找到合适的Croston参数，可能是数据问题")

            logger.info(f"最佳Croston参数: alpha={best_alpha:.2f}, MAPE: {best_mape:.4f}")
            return best_alpha, best_mape, best_result

        # SBA变体方法优化器
        def sba_optimizer(data: pd.Series, alphas: list[float]) -> tuple[float, float, pd.DataFrame]:
            best_mape = float("inf")
            best_alpha = 0.1
            best_result = None

            for alpha in alphas:
                result = sba_method(data, float(alpha), extra_periods)
                forecast = result["Forecast"]

                # 避免除以零
                valid_idx = data != 0
                if valid_idx.sum() == 0:
                    continue

                mape = np.mean(
                    np.abs(
                        (
                            forecast[:-extra_periods].to_numpy()[valid_idx]  # pyright: ignore[reportAttributeAccessIssue]
                            - data.to_numpy()[valid_idx]
                        )
                        / data.to_numpy()[valid_idx]
                    )
                )

                if mape < best_mape:
                    best_alpha = float(alpha)
                    best_mape = float(mape)
                    best_result = result

                logger.debug(f"SBA alpha: {alpha:.2f}, MAPE: {mape:.4f}")

            if best_result is None:
                raise ValueError("无法找到合适的SBA参数，可能是数据问题")

            logger.info(f"最佳SBA参数: alpha={best_alpha:.2f}, MAPE: {best_mape:.4f}")
            return best_alpha, best_mape, best_result

        # TSB变体方法优化器
        def tsb_optimizer(
            data: pd.Series, alphas: list[float], betas: list[float]
        ) -> tuple[float, float, float, pd.DataFrame]:
            best_mape = float("inf")
            best_alpha = 0.1
            best_beta = 0.1
            best_result = None

            for alpha in alphas:
                for beta in betas:
                    result = tsb_method(data, float(alpha), float(beta), extra_periods)
                    forecast = result["Forecast"]

                    # 避免除以零
                    valid_idx = data != 0
                    if valid_idx.sum() == 0:
                        continue

                    mape = np.mean(
                        np.abs(
                            (
                                forecast[:-extra_periods].to_numpy()[valid_idx]  # pyright: ignore[reportAttributeAccessIssue]
                                - data.to_numpy()[valid_idx]
                            )
                            / data.to_numpy()[valid_idx]
                        )
                    )

                    if mape < best_mape:
                        best_alpha = float(alpha)
                        best_beta = float(beta)
                        best_mape = float(mape)
                        best_result = result

                    logger.debug(f"TSB alpha: {alpha:.2f}, beta: {beta:.2f}, MAPE: {mape:.4f}")

            if best_result is None:
                raise ValueError("无法找到合适的TSB参数，可能是数据问题")

            logger.info(f"最佳TSB参数: alpha={best_alpha:.2f}, beta={best_beta:.2f}, MAPE: {best_mape:.4f}")
            return best_alpha, best_beta, best_mape, best_result

        # 执行预测
        results = {}
        forecasts = {}

        # 标准Croston方法
        alpha_cst = mape_cst = result_cst = None
        if "croston" in methods:
            alpha_cst, mape_cst, result_cst = cst_optimizer(data_series, alpha_range)
            results["croston"] = (alpha_cst, mape_cst)
            if result_cst is not None:
                forecasts["croston"] = result_cst["Forecast"]

        # SBA变体
        alpha_sba = mape_sba = result_sba = None
        if "sba" in methods:
            alpha_sba, mape_sba, result_sba = sba_optimizer(data_series, alpha_range)
            results["sba"] = (alpha_sba, mape_sba)
            if result_sba is not None:
                forecasts["sba"] = result_sba["Forecast"]

        # TSB变体
        alpha_tsb = beta_tsb = mape_tsb = result_tsb = None
        if "tsb" in methods:
            alpha_tsb, beta_tsb, mape_tsb, result_tsb = tsb_optimizer(data_series, alpha_range, beta_range)
            results["tsb"] = (alpha_tsb, beta_tsb, mape_tsb)
            if result_tsb is not None:
                forecasts["tsb"] = result_tsb["Forecast"]

        # 选择最佳方法
        best_method = None
        best_mape = float("inf")
        best_forecast = None

        for method in results:
            if method == "croston" and mape_cst is not None and mape_cst < best_mape:
                best_method = method
                best_mape = mape_cst
                best_forecast = forecasts.get("croston")
            elif method == "sba" and mape_sba is not None and mape_sba < best_mape:
                best_method = method
                best_mape = mape_sba
                best_forecast = forecasts.get("sba")
            elif method == "tsb" and mape_tsb is not None and mape_tsb < best_mape:
                best_method = method
                best_mape = mape_tsb
                best_forecast = forecasts.get("tsb")

        logger.info(f"最佳预测方法: {best_method}, MAPE: {best_mape:.4f}")

        # 计算其他评估指标
        mae = mse = rmse = r_squared = 0.0

        if best_forecast is not None:
            # 只计算非零值的评估指标
            valid_idx = data_series != 0
            if valid_idx.sum() > 0:
                actual = data_series.to_numpy()[valid_idx]
                pred = best_forecast[:-extra_periods].to_numpy()[valid_idx]

                mae = np.mean(np.abs(pred - actual))
                mse = np.mean((pred - actual) ** 2)
                rmse = np.sqrt(mse)

                # R-squared
                ss_res = np.sum((actual - pred) ** 2)
                ss_tot = np.sum((actual - np.mean(actual)) ** 2)
                r_squared = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0

        # 创建图表
        image_bytes = None
        if enable_diagnostics:
            _, axes = plt.subplots(2, 1, figsize=(12, 10))

            # 上图: 原始数据和所有预测
            axes[0].plot(df_work[time_column], data_series, label="原始数据", color="black")

            colors = {"croston": "green", "sba": "blue", "tsb": "red"}
            labels = {
                "croston": f"Croston (α={alpha_cst:.2f}, MAPE={mape_cst:.2%})",
                "sba": f"SBA (α={alpha_sba:.2f}, MAPE={mape_sba:.2%})",
                "tsb": f"TSB (α={alpha_tsb:.2f}, β={beta_tsb:.2f}, MAPE={mape_tsb:.2%})",
            }

            for method, forecast in forecasts.items():
                if method in colors and forecast is not None:
                    axes[0].plot(
                        df_work[time_column],
                        forecast[:-extra_periods],
                        label=labels.get(method),
                        color=colors.get(method),
                    )

            axes[0].set_title(f"{column_label or target_column} - 间歇性需求预测方法对比")
            axes[0].set_xlabel("日期")
            axes[0].set_ylabel("需求")
            axes[0].legend()
            axes[0].grid(visible=True, linestyle="--", linewidth=0.5)

            # 下图：最佳预测方法的残差分析
            if best_method is not None and best_forecast is not None:
                residuals = data_series.to_numpy() - best_forecast[:-extra_periods].to_numpy()
                axes[1].scatter(df_work[time_column], residuals, color="purple", alpha=0.6)
                axes[1].axhline(y=0, color="r", linestyle="-")
                axes[1].set_title(f"最佳预测方法({best_method.upper()})残差分析")
                axes[1].set_xlabel("日期")
                axes[1].set_ylabel("残差")
                axes[1].grid(visible=True, linestyle="--", linewidth=0.5)

                # 标出零需求点
                zero_idx = data_series == 0
                if zero_idx.sum() > 0:
                    axes[0].scatter(
                        df_work[time_column][zero_idx],
                        data_series[zero_idx],
                        color="orange",
                        marker="x",
                        label="零需求点",
                    )
                    axes[0].legend()

            plt.tight_layout()

            # 保存图表
            with io.BytesIO() as buf:
                plt.savefig(buf, format="png")
                buf.seek(0)
                image_bytes = buf.getvalue()

            plt.close()

        # 提取最佳预测的实际值和预测值
        actual_values = data_series.to_numpy().tolist()
        predicted_values = []
        if best_forecast is not None:
            predicted_values = best_forecast[:-extra_periods].to_numpy().tolist()

        # 创建结果对象
        result = CrostonAnalysisResult(
            # 基本信息
            algorithm_name="CrostonForecast",
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
            # Croston原始方法
            alpha_cst=alpha_cst or 0.0,
            mape_cst=mape_cst * 100 if mape_cst else 0.0,  # 转换为百分比
            # SBA变体
            alpha_sba=alpha_sba or 0.0,
            mape_sba=mape_sba * 100 if mape_sba else 0.0,  # 转换为百分比
            # TSB变体
            alpha_tsb=alpha_tsb or 0.0,
            beta_tsb=beta_tsb or 0.0,
            mape_tsb=mape_tsb * 100 if mape_tsb else 0.0,  # 转换为百分比
            # 间歇性指标
            zero_percentage=zero_percentage,
            best_method=best_method or "",
            # 预测数据
            actual_values=actual_values,
            predicted_values=predicted_values,
            # 诊断信息
            warnings=warnings_list,
            execution_time=time.time() - start_time,
        )

        logger.info(f"Croston分析完成，执行时间: {result.execution_time:.2f}秒")
        return result, image_bytes

    except Exception as e:
        logger.exception("Croston分析失败")
        raise RuntimeError(f"Croston分析失败: {e}") from e
