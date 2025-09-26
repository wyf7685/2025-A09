"""
随机森林预测算法模块

本模块实现了基于随机森林的时间序列预测算法，
用于预测备件需求，采用标准化的接口和结果格式。
"""

import io
import time
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ..log import logger
from .analysis_results import RandomForestAnalysisResult


def forest_forecast_impl(
    df: pd.DataFrame,
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
) -> tuple[RandomForestAnalysisResult, bytes | None]:
    """
    随机森林预测算法实现函数

    Args:
        df: 输入数据框
        target_column: 目标预测列名
        time_column: 时间列名，默认为"time"
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
        tuple: (RandomForestAnalysisResult, bytes | None)
            - RandomForestAnalysisResult: 预测分析结果对象
            - bytes: PNG格式的图像数据(如果启用诊断)
    """
    start_time = time.time()
    warnings_list = []

    # 默认参数设置
    if n_estimators_range is None:
        n_estimators_range = list(range(5, 101, 5))
    if max_depth_range is None:
        max_depth_range = list(range(5, 101, 5))

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
        df_work = cast("pd.DataFrame", df[[time_column, target_column]].copy())

        # 特征工程
        # 检查时间列是否包含季度信息（"第x季度"）
        if df_work[time_column].iloc[0].find("季度") > -1:
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
                warnings_list.append(f"无法解析时间列为日期: {e!r}")
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

        # 网格搜索最佳参数
        min_mape = float("inf")
        best_n_estimators = None
        best_max_depth = None
        best_predicted = None
        best_model = None

        # 循环尝试不同的参数组合
        for n_estimators in n_estimators_range:
            for max_depth in max_depth_range:
                # 创建和训练随机森林模型
                rf_model = RandomForestRegressor(
                    n_estimators=int(n_estimators), max_depth=max_depth, random_state=random_state
                )
                rf_model.fit(X_train, y_train)

                # 在测试集上评估模型性能
                y_pred = rf_model.predict(X_test)
                # 避免除以零
                non_zero_indices = y_test != 0
                if sum(non_zero_indices) > 0:
                    mape = (
                        np.mean(
                            np.abs((y_test[non_zero_indices] - y_pred[non_zero_indices]) / y_test[non_zero_indices])
                        )
                        * 100
                    )
                else:
                    mape = np.mean(np.abs(y_test - y_pred))

                # 更新最小 MAPE 和对应的参数组合
                if mape < min_mape:
                    min_mape = mape
                    best_n_estimators = n_estimators
                    best_max_depth = max_depth
                    best_predicted = y_pred
                    best_model = rf_model

                # 记录参数组合和性能
                logger.debug("n_estimators=%d, max_depth=%d, MAPE=%f", n_estimators, max_depth, mape)

        # 如果没有找到最佳模型，抛出异常
        if best_model is None or best_predicted is None:
            raise RuntimeError("无法找到有效的随机森林模型")

        # 记录最佳参数组合和最小的 MAPE
        logger.info(
            "Best parameters: n_estimators=%d, max_depth=%d, Min MAPE=%f", best_n_estimators, best_max_depth, min_mape
        )

        # 计算其他评估指标
        mae = mean_absolute_error(y_test, best_predicted)
        mse = mean_squared_error(y_test, best_predicted)
        rmse = np.sqrt(mse)
        r_squared = r2_score(y_test, best_predicted)

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
        result = RandomForestAnalysisResult(
            algorithm_name="随机森林预测",
            target_column=target_column,
            total_samples=len(df_work),
            train_samples=len(train),
            test_samples=len(test),
            train_start_date=train_start_date,
            train_end_date=train_end_date,
            test_start_date=test_start_date,
            test_end_date=test_end_date,
            mape=min_mape,
            mae=mae,
            mse=mse,
            rmse=rmse,
            r_squared=r_squared,
            actual_values=y_test.tolist(),
            predicted_values=best_predicted.tolist(),  # pyright: ignore[reportArgumentType]
            warnings=warnings_list,
            execution_time=time.time() - start_time,
            n_estimators=best_n_estimators if best_n_estimators is not None else 0,
            max_depth=best_max_depth if best_max_depth is not None else 0,
            feature_importances={k: float(v) for k, v in feature_importances.items()},
        )

        # 生成诊断图表
        image_bytes = None
        if enable_diagnostics:
            plt.figure(figsize=(10, 6))

            # 绘制整个时间序列和测试集的预测值
            all_times = df_work[time_column].tolist()
            all_values = df_work[target_column].tolist()

            plt.plot(all_times, all_values, "k-", label=f"实际{column_label}")

            # 获取测试集时间和预测值
            test_times = test[time_column].tolist()
            plt.plot(test_times, best_predicted, "r-", label="预测值")

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
                        future_times = [f"Future {i + 1}" for i in range(extra_periods)]

                # 绘制未来预测
                plt.plot(future_times, future_predictions, "g--", label="未来预测")

            # 设置图表标题和标签
            title = plot_title if plot_title else f"随机森林预测 - {column_label}"
            plt.title(f"{title}\nMAPE: {min_mape:.2f}%, RMSE: {rmse:.2f}, R²: {r_squared:.2f}")
            plt.xlabel("时间")
            plt.ylabel(column_label)
            plt.xticks(rotation=45)
            plt.grid(True, linestyle="--", alpha=0.7)
            plt.legend()
            plt.tight_layout()

            # 将图表保存为二进制数据
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100)
            buf.seek(0)
            image_bytes = buf.getvalue()
            plt.close()

        return result, image_bytes

    except Exception as e:
        logger.exception("随机森林预测失败")
        # 创建一个包含错误信息的结果
        result = RandomForestAnalysisResult(
            algorithm_name="随机森林预测",
            target_column=target_column,
            total_samples=0,
            train_samples=0,
            test_samples=0,
            train_start_date="",
            train_end_date="",
            test_start_date="",
            test_end_date="",
            mape=0.0,
            warnings=[f"预测失败: {e!r}"],
            execution_time=time.time() - start_time,
        )
        return result, None
