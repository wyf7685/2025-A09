"""
BP神经网络预测模块

该模块实现了基于BP神经网络的时间序列预测功能。
主要功能:
- 数据预处理和特征工程
- BP神经网络模型构建和训练
- 超参数优化（输入层和隐含层神经元数量）
- 模型评估和结果可视化
- 批量预测和结果导出
"""

import io
import logging
import time
from typing import TYPE_CHECKING, Any, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler
from tensorflow.python.keras.initializers.initializers_v2 import GlorotUniform
from tensorflow.python.keras.layers import Dense
from tensorflow.python.keras.models import Sequential
from tensorflow.python.keras.optimizer_v1 import Adam

from .analysis_results import BPNNAnalysisResult

if TYPE_CHECKING:
    from tensorflow.python.keras.callbacks import History

logger = logging.getLogger(__name__)


def bp_forecast_impl(
    df: pd.DataFrame,
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
) -> tuple[BPNNAnalysisResult, bytes | None]:
    """
    BP神经网络预测算法实现函数

    Args:
        df: 输入数据框
        target_column: 目标预测列名
        time_column: 时间列名，默认为"time"
        input_sizes: 输入层尺寸范围，默认为[2,3,4,5,6]
        hidden_sizes: 隐含层尺寸范围，默认为[2,4,6,8,10,12]
        epochs: 训练轮数，默认为100
        batch_size: 批次大小，默认为16
        learning_rate: 学习率，默认为0.001
        test_size: 测试集比例，默认为0.2
        random_state: 随机种子，默认为42
        enable_diagnostics: 是否启用诊断，默认为True
        column_label: 图表中显示的列标签，默认使用target_column值
        plot_title: 图表标题，默认为None(自动生成)

    Returns:
        tuple: (BPNNAnalysisResult, bytes | None)
            - BPNNAnalysisResult: 预测分析结果对象
            - bytes: PNG格式的图像数据(如果启用诊断)
    """
    start_time = time.time()
    warnings_list = []

    # 默认参数设置
    if input_sizes is None:
        input_sizes = [2, 3, 4, 5, 6]
    if hidden_sizes is None:
        hidden_sizes = [2, 4, 6, 8, 10, 12]

    if column_label is None:
        column_label = target_column

    try:
        np.random.seed(random_state)
        tf.random.set_seed(random_state)

        # 数据验证
        if target_column not in df.columns:
            raise ValueError(f"目标列 '{target_column}' 不存在")
        if time_column not in df.columns:
            raise ValueError(f"时间列 '{time_column}' 不存在")

        # 构建特征
        df_work = cast("pd.DataFrame", df[[time_column, target_column]]).copy()

        # 解析季度数据为年份和季度
        # has_time_features = False
        if "季度" in str(df_work[time_column].iloc[0]):
            df_work["year"] = df_work[time_column].str.split(" 第").str[0].astype(int)
            df_work["quarter"] = df_work[time_column].str.split("第").str[1].str.replace("季度", "").astype(int)
            # has_time_features = True
        else:
            try:
                # 尝试将时间列解析为日期时间
                df_work["date"] = pd.to_datetime(df_work[time_column])
                df_work["year"] = df_work["date"].dt.year
                df_work["month"] = df_work["date"].dt.month
                df_work["quarter"] = df_work["date"].dt.quarter
                # has_time_features = True
            except Exception:
                warnings_list.append(f"无法将时间列 '{time_column}' 解析为日期格式")

        # 数据规范化
        scaler = MinMaxScaler()
        df_work["normalized_value"] = scaler.fit_transform(df_work[[target_column]])

        # 记录训练和测试数据的日期范围
        train_start_date = df_work[time_column].iloc[0]
        test_end_date = df_work[time_column].iloc[-1]
        split_idx = int((1 - test_size) * len(df_work))
        train_end_date = df_work[time_column].iloc[split_idx - 1]
        test_start_date = df_work[time_column].iloc[split_idx]

        # 用于跟踪最佳模型
        best_model = None
        best_mape = float("inf")
        best_input_size = 0
        best_hidden_size = 0
        best_train_history = None
        best_y_pred = None
        best_y_test = None
        best_test_indices = None

        # 网格搜索最佳参数
        for input_size in input_sizes:
            for hidden_size in hidden_sizes:
                np.random.seed(random_state)
                tf.random.set_seed(random_state)
                logger.info(f"尝试参数组合: 输入层={input_size}, 隐含层={hidden_size}")

                # 创建时间序列数据
                X = []
                y = []

                for i in range(len(df_work) - input_size):
                    X.append(df_work["normalized_value"].iloc[i : i + input_size].values)
                    y.append(df_work["normalized_value"].iloc[i + input_size])

                X = np.array(X)
                y = np.array(y)

                # 划分训练集和测试集
                train_size = int((1 - test_size) * len(X))
                X_train, X_test = X[:train_size], X[train_size:]
                y_train, y_test = y[:train_size], y[train_size:]

                # 测试索引
                test_indices = df_work.index[input_size + train_size : input_size + len(X)]

                # 构建BP神经网络模型
                # 自定义tansig激活函数
                def tansig(x: Any) -> Any:
                    return (2.0 / (1.0 + tf.exp(tf.multiply(-2.0, x)))) - 1.0

                model: Sequential = cast("Sequential", Sequential())
                model.add(
                    Dense(
                        hidden_size,
                        input_dim=input_size,
                        activation=tansig,
                        kernel_initializer=GlorotUniform(seed=random_state),  # pyright: ignore[reportArgumentType]
                    )
                )
                model.add(
                    Dense(
                        1,
                        activation="linear",
                        kernel_initializer=GlorotUniform(seed=random_state),  # pyright: ignore[reportArgumentType]
                    ),
                )

                # 编译模型
                optimizer = Adam(lr=learning_rate)
                model.compile(loss="mean_squared_error", optimizer=optimizer)  # pyright: ignore[reportArgumentType]

                # 训练模型
                history = model.fit(
                    X_train,
                    y_train,
                    epochs=epochs,
                    batch_size=batch_size,
                    validation_split=0.2,
                    verbose=0,  # pyright: ignore[reportArgumentType]
                )
                history = cast("History", history)

                # 预测
                y_pred = model.predict(X_test, verbose=0)

                # 还原预测结果的缩放
                y_test_reshaped = y_test.reshape(-1, 1)
                y_pred_denorm = scaler.inverse_transform(y_pred)
                y_test_denorm = scaler.inverse_transform(y_test_reshaped)

                # 计算性能指标
                mape = np.mean(np.abs((y_pred_denorm - y_test_denorm) / y_test_denorm)) * 100

                logger.info(f"MAPE: {mape:.4f}%")

                if mape < best_mape:
                    best_mape = mape
                    best_input_size = input_size
                    best_hidden_size = hidden_size
                    best_train_history = history.history
                    best_model = model
                    best_y_pred = y_pred_denorm
                    best_y_test = y_test_denorm
                    best_test_indices = test_indices

        if best_test_indices is None or best_y_pred is None or best_y_test is None:
            raise RuntimeError("未能找到合适的参数组合进行预测")

        # 使用最佳参数的最终评估指标
        mae = mean_absolute_error(best_y_test, best_y_pred)
        mse = mean_squared_error(best_y_test, best_y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(best_y_test, best_y_pred)

        # 图表生成（如果启用诊断）
        image_bytes = None
        if enable_diagnostics and best_model is not None:
            plt.figure(figsize=(12, 10))

            # 第一个子图：预测结果
            plt.subplot(2, 1, 1)
            plt.plot(df_work[time_column], df_work[target_column], label="实际值", color="blue")
            plt.plot(
                [df_work[time_column].iloc[i] for i in best_test_indices],
                best_y_pred.flatten(),
                label="BP神经网络预测值",
                color="red",
                linestyle="--",
            )

            # 设置标题和标签
            title = plot_title if plot_title else f"BP神经网络预测 - {column_label}"
            plt.title(title)
            plt.xlabel("时间")
            plt.ylabel(column_label)
            plt.legend()
            plt.grid(True)
            plt.xticks(rotation=45)

            # 第二个子图：训练历史
            if best_train_history:
                plt.subplot(2, 1, 2)
                plt.plot(best_train_history["loss"], label="训练损失")
                if "val_loss" in best_train_history:
                    plt.plot(best_train_history["val_loss"], label="验证损失")
                plt.title("模型训练历史")
                plt.xlabel("Epoch")
                plt.ylabel("损失")
                plt.legend()
                plt.grid(True)

            # 添加模型信息
            info_text = (
                f"最佳参数: 输入层={best_input_size}, 隐含层={best_hidden_size}\n"
                f"性能指标: MAPE={best_mape:.2f}%, MAE={mae:.2f}, RMSE={rmse:.2f}, R²={r2:.2f}"
            )
            plt.figtext(0.02, 0.02, info_text, bbox={"facecolor": "yellow", "alpha": 0.5})

            plt.tight_layout()

            # 将图表转换为PNG格式的字节流
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100)
            buf.seek(0)
            image_bytes = buf.getvalue()
            plt.close()

        # 计算执行时间
        execution_time = time.time() - start_time

        # 构建分析结果
        result = BPNNAnalysisResult(
            algorithm_name="BP神经网络",
            target_column=target_column,
            total_samples=len(df_work),
            train_samples=len(df_work) - len(best_y_test),
            test_samples=len(best_y_test),
            train_start_date=str(train_start_date),
            train_end_date=str(train_end_date),
            test_start_date=str(test_start_date),
            test_end_date=str(test_end_date),
            mape=best_mape,
            mae=mae,
            mse=mse,
            rmse=rmse,
            r_squared=r2,
            actual_values=best_y_test.flatten().tolist(),
            predicted_values=best_y_pred.flatten().tolist(),
            input_size=best_input_size,
            hidden_size=best_hidden_size,
            learning_rate=learning_rate,
            epochs=epochs,
            batch_size=batch_size,
            early_stopping_patience=0,
            loss_history=best_train_history["loss"] if best_train_history else [],
            val_loss_history=best_train_history.get("val_loss", []) if best_train_history else [],
            warnings=warnings_list,
            execution_time=execution_time,
        )

        return result, image_bytes

    except Exception as e:
        logger.exception("BP神经网络预测过程出错")
        # 确保图表被关闭
        plt.close("all")
        raise RuntimeError(f"BP神经网络预测过程出错: {e}") from e
