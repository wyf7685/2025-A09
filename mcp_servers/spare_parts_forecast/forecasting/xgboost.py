"""
XGBoost预测模块 - 基于灰狼优化算法的XGBoost回归预测 - 重构版

该模块实现了使用灰狼优化算法优化XGBoost超参数的时间序列预测功能。
采用标准化的接口和结果格式。

主要功能:
- 数据预处理和特征工程
- 灰狼优化算法实现
- XGBoost模型训练和预测
- 模型评估和结果可视化
"""

import io
import time
from collections.abc import Callable
from typing import Any, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ..log import logger
from .analysis_results import XGBoostAnalysisResult


def xgboost_forecast_impl(
    df: pd.DataFrame,
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
) -> tuple[XGBoostAnalysisResult, bytes | None]:
    """
    XGBoost预测算法实现函数（基于灰狼优化）

    Args:
        df: 输入数据框
        target_column: 目标预测列名
        time_column: 时间列名，默认为"time"
        feature_columns: 特征列名列表，默认为None（自动生成时间特征）
        test_size: 测试集比例，默认为0.2
        learning_rate_range: 学习率范围，默认为[0.01, 0.05, 0.1, 0.2]
        max_depth_range: 最大深度范围，默认为[3, 5, 7, 9]
        n_estimators_range: 估计器数量范围，默认为[50, 100, 200, 300]
        gwo_agents: 灰狼优化算法搜索代理数量，默认为10
        gwo_iterations: 灰狼优化算法最大迭代次数，默认为2
        random_state: 随机种子，默认为42
        extra_periods: 额外预测的期数，默认为0
        enable_diagnostics: 是否启用诊断，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值
        plot_title: 图表标题，默认为None(自动生成)

    Returns:
        tuple: (XGBoostAnalysisResult, bytes | None)
            - XGBoostAnalysisResult: 预测分析结果对象
            - bytes: PNG格式的图像数据(如果启用诊断)
    """
    start_time = time.time()
    warnings_list = []

    # 默认参数设置
    if learning_rate_range is None:
        learning_rate_range = [0.01, 0.05, 0.1, 0.2]
    if max_depth_range is None:
        max_depth_range = [3, 5, 7, 9]
    if n_estimators_range is None:
        n_estimators_range = [50, 100, 200, 300]

    try:
        # 数据验证
        if target_column not in df.columns:
            raise ValueError(f"目标列 '{target_column}' 不存在")
        if time_column not in df.columns:
            raise ValueError(f"时间列 '{time_column}' 不存在")

        # 提取相关列并保存原始列名用于展示
        if column_label is None:
            column_label = target_column

        # 构建特征
        df_work = cast("pd.DataFrame", df[[time_column, target_column]]).copy()

        # 特征工程
        # 检查时间列是否包含季度信息（"第x季度"）
        if pd.api.types.is_string_dtype(df_work[time_column]) and df_work[time_column].iloc[0].find("季度") > -1:
            # 解析季度数据为年份和季度
            df_work["year"] = df_work[time_column].str.split(" 第").str[0].astype(int)
            df_work["quarter"] = df_work[time_column].str.split("第").str[1].str.replace("季度", "").astype(int)
        else:
            # 如果不是季度数据，尝试解析为日期，提取年份和月份
            try:
                df_work["date"] = pd.to_datetime(df_work[time_column])
                df_work["year"] = df_work["date"].dt.year
                df_work["month"] = df_work["date"].dt.month
                if "quarter" not in df_work.columns:
                    df_work["quarter"] = df_work["date"].dt.quarter
            except Exception as e:
                warnings_list.append(f"无法解析时间列为日期: {e!s}")
                df_work["time_index"] = range(len(df_work))
                feature_columns = ["time_index"]

        # 使用指定的特征列或默认创建的特征
        if feature_columns is None:
            if "year" in df_work.columns and "quarter" in df_work.columns:
                feature_columns = ["year", "quarter"]
            elif "year" in df_work.columns and "month" in df_work.columns:
                feature_columns = ["year", "month"]
            elif "time_index" in df_work.columns:
                feature_columns = ["time_index"]
            else:
                raise ValueError("无法自动创建有效的特征，请指定feature_columns")

        # 划分训练和测试集
        split_idx = int((1 - test_size) * len(df_work))
        train = df_work.iloc[:split_idx]
        test = df_work.iloc[split_idx:]

        # 记录训练和测试集的日期范围
        train_start_date = str(train[time_column].iloc[0])
        train_end_date = str(train[time_column].iloc[-1])
        test_start_date = str(test[time_column].iloc[0])
        test_end_date = str(test[time_column].iloc[-1])

        # 准备特征和目标变量
        X_train = train[feature_columns]
        y_train = train[target_column]
        X_test = test[feature_columns]
        y_test = test[target_column]

        # 设置灰狼优化参数
        dim = 3  # 优化三个变量：max_depth, learning_rate, n_estimators
        lb = 0  # 下界
        ub = 1  # 上界

        # 定义用于灰狼优化的适应度函数
        def fitness_function(positions: np.ndarray) -> tuple[float, xgb.XGBRegressor, np.ndarray]:
            """基于参数位置计算模型性能的适应度函数"""
            # 归一化参数到实际范围
            depth_idx = int(positions[0] * len(max_depth_range))
            lr_idx = int(positions[1] * len(learning_rate_range))
            est_idx = int(positions[2] * len(n_estimators_range))

            # 确保索引在有效范围内
            depth_idx = max(0, min(depth_idx, len(max_depth_range) - 1))
            lr_idx = max(0, min(lr_idx, len(learning_rate_range) - 1))
            est_idx = max(0, min(est_idx, len(n_estimators_range) - 1))

            # 获取实际参数值
            max_depth = max_depth_range[depth_idx]
            learning_rate = learning_rate_range[lr_idx]
            n_estimators = n_estimators_range[est_idx]

            # 创建和训练模型
            model = xgb.XGBRegressor(
                max_depth=max_depth, learning_rate=learning_rate, n_estimators=n_estimators, random_state=random_state
            )
            model.fit(X_train, y_train)

            # 预测和评估
            y_pred = model.predict(X_test)

            # 避免除以零
            non_zero_indices = y_test != 0
            if sum(non_zero_indices) > 0:
                mape = (
                    np.mean(np.abs((y_test[non_zero_indices] - y_pred[non_zero_indices]) / y_test[non_zero_indices]))
                    * 100
                )
            else:
                mape = np.mean(np.abs(y_test - y_pred))

            # 返回错误率作为适应度（越小越好）、模型和预测值
            return mape / 100, model, y_pred

        # 执行灰狼优化算法
        logger.info("开始执行灰狼优化算法")
        best_position, best_score, best_model, best_pred, gwo_history = _gwo_optimizer(
            fitness_function, dim, lb, ub, gwo_agents, gwo_iterations
        )

        # 解析最佳参数
        depth_idx = int(best_position[0] * len(max_depth_range))
        lr_idx = int(best_position[1] * len(learning_rate_range))
        est_idx = int(best_position[2] * len(n_estimators_range))

        # 确保索引在有效范围内
        depth_idx = max(0, min(depth_idx, len(max_depth_range) - 1))
        lr_idx = max(0, min(lr_idx, len(learning_rate_range) - 1))
        est_idx = max(0, min(est_idx, len(n_estimators_range) - 1))

        # 获取实际参数值
        best_depth = max_depth_range[depth_idx]
        best_lr = learning_rate_range[lr_idx]
        best_estimators = n_estimators_range[est_idx]

        logger.info(f"最优深度: {best_depth}")
        logger.info(f"最优学习率: {best_lr}")
        logger.info(f"最优估计器数量: {best_estimators}")

        # 计算其他评估指标
        mae = mean_absolute_error(y_test, best_pred)
        mse = mean_squared_error(y_test, best_pred)
        rmse = np.sqrt(mse)
        r_squared = r2_score(y_test, best_pred)

        # 获取特征重要性
        feature_importances = {
            feature_columns[i]: importance for i, importance in enumerate(best_model.feature_importances_)
        }

        # 进行额外的预测（如果需要）
        future_predictions = []
        if extra_periods > 0:
            # 为预测创建特征
            last_time = df_work.iloc[-1]
            future_features = []

            for i in range(1, extra_periods + 1):
                if "year" in df_work.columns and "quarter" in df_work.columns:
                    # 处理季度数据
                    next_quarter = last_time["quarter"] + i
                    year_add = (next_quarter - 1) // 4
                    quarter = (next_quarter - 1) % 4 + 1
                    next_year = last_time["year"] + year_add
                    future_features.append([next_year, quarter])
                elif "year" in df_work.columns and "month" in df_work.columns:
                    # 处理月度数据
                    next_month = last_time["month"] + i
                    year_add = (next_month - 1) // 12
                    month = (next_month - 1) % 12 + 1
                    next_year = last_time["year"] + year_add
                    future_features.append([next_year, month])
                elif "time_index" in df_work.columns:
                    # 处理索引数据
                    future_features.append([len(df_work) + i - 1])

            # 创建预测数据框
            future_df = pd.DataFrame(future_features, columns=feature_columns)  # pyright: ignore[reportArgumentType]
            future_predictions = best_model.predict(future_df).tolist()

        # 创建结果对象
        result = XGBoostAnalysisResult(
            algorithm_name="XGBoost预测(灰狼优化)",
            target_column=target_column,
            total_samples=len(df_work),
            train_samples=len(train),
            test_samples=len(test),
            train_start_date=train_start_date,
            train_end_date=train_end_date,
            test_start_date=test_start_date,
            test_end_date=test_end_date,
            mape=best_score * 100,  # 转换回百分比
            mae=mae,
            mse=mse,
            rmse=rmse,
            r_squared=r_squared,
            actual_values=y_test.tolist(),
            predicted_values=best_pred.tolist(),
            warnings=warnings_list,
            execution_time=time.time() - start_time,
            learning_rate=best_lr,
            max_depth=best_depth,
            n_estimators=best_estimators,
            feature_importances=feature_importances,
            early_stopping_rounds=0,  # 没有使用早停
            gwo_iterations=gwo_iterations,
            gwo_agents=gwo_agents,
            best_position=best_position.tolist(),
        )

        # 生成诊断图表
        image_bytes = None
        if enable_diagnostics:
            plt.figure(figsize=(12, 8))

            # 创建2x2的子图布局
            fig, axs = plt.subplots(2, 2, figsize=(12, 10))

            # 1. 真实值vs预测值图
            axs[0, 0].plot(test[time_column], y_test, "k-", label="实际值")
            axs[0, 0].plot(test[time_column], best_pred, "r-", label="预测值")
            axs[0, 0].set_title("测试集：实际值 vs 预测值")
            axs[0, 0].set_xlabel("时间")
            axs[0, 0].set_ylabel(column_label)
            axs[0, 0].legend()
            axs[0, 0].grid(True, linestyle="--", alpha=0.7)
            plt.setp(axs[0, 0].xaxis.get_majorticklabels(), rotation=45)

            # 2. 整个时间序列和未来预测
            all_times = df_work[time_column].tolist()
            all_values = df_work[target_column].tolist()

            axs[0, 1].plot(all_times, all_values, "k-", label="历史数据")

            # 获取测试集时间和预测值
            test_times = test[time_column].tolist()
            axs[0, 1].plot(test_times, best_pred, "r-", label="测试集预测")

            # 添加未来预测（如果有）
            if future_predictions and extra_periods > 0:
                # 创建未来的时间标签
                future_times = []
                last_time_str = df_work[time_column].iloc[-1]

                # 根据数据格式创建未来时间标签
                if "季度" in last_time_str:
                    # 季度数据
                    parts = last_time_str.split(" 第")
                    year = int(parts[0])
                    quarter = int(parts[1].replace("季度", ""))

                    for i in range(1, extra_periods + 1):
                        next_quarter = quarter + i
                        year_add = (next_quarter - 1) // 4
                        q = (next_quarter - 1) % 4 + 1
                        next_year = year + year_add
                        future_times.append(f"{next_year} 第{q}季度")
                else:
                    # 尝试作为日期处理
                    try:
                        last_date = pd.to_datetime(last_time_str)
                        for i in range(1, extra_periods + 1):
                            if "month" in df_work.columns:
                                # 月度数据
                                future_times.append((last_date + pd.DateOffset(months=i)).strftime("%Y-%m"))
                            else:
                                # 默认为天
                                future_times.append((last_date + pd.DateOffset(days=i)).strftime("%Y-%m-%d"))
                    except Exception:
                        # 简单递增
                        future_times = [f"预测 {i + 1}" for i in range(extra_periods)]

                # 绘制未来预测
                axs[0, 1].plot(future_times, future_predictions, "g--", label="未来预测")

            axs[0, 1].set_title("整个时间序列预测")
            axs[0, 1].set_xlabel("时间")
            axs[0, 1].set_ylabel(column_label)
            axs[0, 1].legend()
            axs[0, 1].grid(True, linestyle="--", alpha=0.7)
            plt.setp(axs[0, 1].xaxis.get_majorticklabels(), rotation=45)

            # 3. 残差分析图
            residuals = y_test - best_pred
            axs[1, 0].scatter(best_pred, residuals)
            axs[1, 0].axhline(y=0, color="r", linestyle="-")
            axs[1, 0].set_title("残差分析")
            axs[1, 0].set_xlabel("预测值")
            axs[1, 0].set_ylabel("残差")
            axs[1, 0].grid(True, linestyle="--", alpha=0.7)

            # 4. 优化过程图
            iterations = list(range(1, gwo_iterations + 1))
            scores = list(gwo_history)
            axs[1, 1].plot(iterations, scores, "b-o")
            axs[1, 1].set_title("灰狼优化算法收敛过程")
            axs[1, 1].set_xlabel("迭代次数")
            axs[1, 1].set_ylabel("最佳适应度（错误率）")
            axs[1, 1].grid(True, linestyle="--", alpha=0.7)

            # 设置总标题
            title = plot_title if plot_title else f"XGBoost预测(灰狼优化) - {column_label}"
            fig.suptitle(f"{title}\nMAPE: {best_score * 100:.2f}%, RMSE: {rmse:.2f}, R²: {r_squared:.2f}", fontsize=16)

            # 调整布局
            plt.tight_layout(rect=(0, 0, 1, 0.95))

            # 将图表保存为二进制数据
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100)
            buf.seek(0)
            image_bytes = buf.getvalue()
            plt.close()

        return result, image_bytes

    except Exception as e:
        logger.exception("XGBoost预测失败")
        # 创建一个包含错误信息的结果
        result = XGBoostAnalysisResult(
            algorithm_name="XGBoost预测(灰狼优化)",
            target_column=target_column,
            total_samples=0,
            train_samples=0,
            test_samples=0,
            train_start_date="",
            train_end_date="",
            test_start_date="",
            test_end_date="",
            mape=0.0,
            warnings=[f"预测失败: {e!s}"],
            execution_time=time.time() - start_time,
        )
        return result, None


def _gwo_optimizer(
    fitness_function: Callable[[np.ndarray], tuple[float, xgb.XGBRegressor, np.ndarray]],
    dim: int,
    lb: float,
    ub: float,
    search_agents: int = 10,
    max_iterations: int = 10,
) -> tuple[np.ndarray, float, Any, np.ndarray, list[float]]:
    """
    灰狼优化算法实现

    Args:
        fitness_function: 适应度函数，接受位置数组并返回(score, model, predictions)
        dim: 优化维度
        lb: 参数下界
        ub: 参数上界
        search_agents: 搜索代理数量
        max_iterations: 最大迭代次数

    Returns:
        tuple: (最佳位置，最佳分数，最佳模型，最佳预测，迭代历史)
    """
    # 初始化三只首领灰狼位置和分数
    alpha_position = np.zeros(dim)
    beta_position = np.zeros(dim)
    delta_position = np.zeros(dim)

    alpha_score = float("inf")
    beta_score = float("inf")
    delta_score = float("inf")
    alpha_model = None
    alpha_pred = None

    # 初始化种群位置
    positions = np.random.uniform(lb, ub, (search_agents, dim))

    # 记录每次迭代的最佳适应度
    convergence = []

    # 迭代优化
    for t in range(max_iterations):
        # 对每个搜索代理评估适应度
        for i in range(search_agents):
            # 边界处理
            positions[i] = np.clip(positions[i], lb, ub)

            # 计算当前位置的适应度
            fitness, model, pred = fitness_function(positions[i])

            # 更新Alpha、Beta、Delta
            if fitness < alpha_score:
                delta_score = beta_score
                delta_position = beta_position.copy()

                beta_score = alpha_score
                beta_position = alpha_position.copy()

                alpha_score = fitness
                alpha_position = positions[i].copy()
                alpha_model = model
                alpha_pred = pred

            elif fitness < beta_score:
                delta_score = beta_score
                delta_position = beta_position.copy()

                beta_score = fitness
                beta_position = positions[i].copy()

            elif fitness < delta_score:
                delta_score = fitness
                delta_position = positions[i].copy()

        # 记录当前迭代的最佳适应度
        convergence.append(alpha_score)

        # 更新a参数
        a = 2 - t * (2 / max_iterations)

        # 更新每个搜索代理的位置
        for i in range(search_agents):
            for j in range(dim):
                # 计算Alpha围猎行为
                r1 = np.random.rand()
                r2 = np.random.rand()
                A1 = 2 * a * r1 - a
                C1 = 2 * r2
                D_alpha = abs(C1 * alpha_position[j] - positions[i, j])
                X1 = alpha_position[j] - A1 * D_alpha

                # 计算Beta围猎行为
                r1 = np.random.rand()
                r2 = np.random.rand()
                A2 = 2 * a * r1 - a
                C2 = 2 * r2
                D_beta = abs(C2 * beta_position[j] - positions[i, j])
                X2 = beta_position[j] - A2 * D_beta

                # 计算Delta围猎行为
                r1 = np.random.rand()
                r2 = np.random.rand()
                A3 = 2 * a * r1 - a
                C3 = 2 * r2
                D_delta = abs(C3 * delta_position[j] - positions[i, j])
                X3 = delta_position[j] - A3 * D_delta

                # 更新位置
                positions[i, j] = (X1 + X2 + X3) / 3

    assert alpha_pred is not None
    return alpha_position, alpha_score, alpha_model, alpha_pred, convergence
