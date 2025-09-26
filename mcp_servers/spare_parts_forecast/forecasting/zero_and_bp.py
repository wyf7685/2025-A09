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

import logging
import warnings
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 可选导入 TensorFlow：避免直接 ImportError 影响整个包
try:
    import tensorflow as tf  # type: ignore
    from tensorflow.keras.layers import Dense  # type: ignore
    from tensorflow.keras.models import Sequential  # type: ignore
    from tensorflow.keras.optimizers import Adam  # type: ignore

    _TF_AVAILABLE = True
    _TF_IMPORT_ERROR: Exception | None = None
except Exception as _e:  # 捕获所有异常（包含可能的硬件 / DLL 兼容问题）
    tf = None  # type: ignore
    Dense = Sequential = Adam = None  # type: ignore
    _TF_AVAILABLE = False
    _TF_IMPORT_ERROR = _e

# 忽略警告
warnings.filterwarnings("ignore")

# def preprocess_data() -> pd.DataFrame:
#     """
#     数据预处理函数 - 创建示例数据

#     Returns:
#         pd.DataFrame: 预处理后的数据框
#     """
#     # 创建示例时间序列数据
#     time_periods = []
#     values = []

#     # 生成2018-2025年的季度数据
#     for year in range(2018, 2026):
#         for quarter in range(1, 5):
#             time_periods.append(f"{year} 第{quarter}季度")
#             # 生成带有趋势的随机值
#             base_value = 1000 + (year - 2018) * 100 + quarter * 50
#             noise = np.random.normal(0, 100)
#             values.append(base_value + noise)

#     return pd.DataFrame({"time": time_periods[: len(time_periods)], "values": values[: len(values)]})


__all__ = ["zero_and_bp_predict"]


def zero_and_bp_predict(column_index: int, df: pd.DataFrame) -> tuple[list[str], float]:
    """
    BP神经网络预测主函数

    Args:
        column_index: 数据列索引

    Returns:
        tuple: (列名列表, 最小MAPE值)
    """
    if not _TF_AVAILABLE:
        raise RuntimeError(
            "TensorFlow 未可用，无法执行 BP 神经网络预测。"
            f"\n原因: {_TF_IMPORT_ERROR!r}"
            "\n解决办法: (1) 使用受支持的 Python 版本(建议 3.10~3.12);\n"
            "(2) 确认已安装 'tensorflow'; (3) 若仅需其它算法可忽略本函数。"
        )

    # 读取列索引名（当前示例生成模拟数据，实际可替换为真实数据加载）
    # df = preprocess_data()
    col = df.columns

    # 正常bp（循环）
    def bp_neural_network(sr: int, yh: int) -> tuple[float, np.ndarray, pd.DataFrame, pd.Index]:
        """
        BP神经网络模型训练和预测

        Args:
            sr: 输入层神经元数量
            yh: 隐含层神经元数量
            isplt: 是否绘图

        Returns:
            tuple: (MAPE值, 预测值, 数据, 测试索引)
        """
        # 读取数据
        data = df

        # 选择指定列
        data = df.iloc[:, [0, column_index]] if len(df.columns) > column_index else df.iloc[:, [0, 1]]
        data.columns = ["time", "values"]

        # 解析季度数据为年份和季度
        data["Year"] = data["time"].str.split(" 第").str[0].astype(int)
        data["Quarter"] = data["time"].str.split("第").str[1].str.replace("季度", "").astype(int)

        # 数据预处理
        scaler = MinMaxScaler()
        data["value"] = scaler.fit_transform(data[["values"]])

        # 创建数据集
        window_size = sr  # 设置窗口大小
        X = []
        y = []

        for i in range(len(data) - window_size):
            X.append(data["value"].to_numpy()[i : i + window_size])
            y.append(data["value"].to_numpy()[i + window_size])

        X = np.array(X)
        y = np.array(y)

        # 划分训练集和测试集
        train_size = int(0.8 * len(X))
        X_train, X_test = X[:train_size], X[train_size:]
        y_train, y_test = y[:train_size], y[train_size:]

        # 作图索引设置
        y_test_indices = data.index[-(len(y_test)) :]

        # 自定义tansig激活函数
        def tansig(x: Any) -> Any:  # 自定义双曲正切激活函数
            return (2.0 / (1.0 + tf.exp(tf.multiply(-2.0, x)))) - 1.0  # type: ignore[attr-defined]

        # 构建BP神经网络模型
        model = Sequential()  # type: ignore[call-arg]
        model.add(Dense(yh, input_dim=window_size, activation=tansig))  # type: ignore[misc]
        model.add(Dense(1, activation="linear"))  # type: ignore[misc]

        # 编译模型
        optimizer = Adam(learning_rate=0.001)  # type: ignore[call-arg]
        model.compile(loss="mean_squared_error", optimizer=optimizer)  # type: ignore[attr-defined]

        # 训练模型
        model.fit(X_train, y_train, epochs=100, batch_size=16, verbose=0)

        # 使用模型进行预测
        y_pred = model.predict(X_test, verbose=0)
        # 还原预测结果的缩放
        y_test = y_test.reshape(-1, 1)

        y_pred = scaler.inverse_transform(y_pred)
        y_test = scaler.inverse_transform(y_test)

        logger.info(f"预测值: {y_pred.flatten()}")
        logger.info(f"真实值: {y_test.flatten()}")

        # 计算预测结果的MAPE
        mape = np.mean(np.abs((y_pred - y_test) / y_test))
        return float(mape), y_pred, data, y_test_indices

    # 循环遍历，取最优的参数
    min_mape = 999.0
    best_sr = 0
    best_yh = 0

    i = 0
    for sr in range(2, 7):
        for yh in range(2, 13):
            mape, y_pred, data, y_test_indices = bp_neural_network(sr, yh)
            i = i + 1
            if mape < min_mape:
                min_mape = mape
                best_sr = sr
                best_yh = yh
                # 将预测结果与真实数据绘制成图表（仅在发现更优时）
                plt.rcParams["font.family"] = "SimHei"
                plt.rcParams["font.size"] = 12
                _, ax = plt.subplots(figsize=(10, 6))
                ax.plot(data["time"], data["values"], label="真实数量", color="black")
                ax.plot(y_test_indices, y_pred, label="预测数量", color="r")
                plt.xlabel("日期")
                plt.ylabel("数量")
                plt.title(f"物料号：{col[column_index]}\nMAPE: {round(mape, 4)}")
                plt.legend()
                plt.grid(grid=True, linestyle="--", linewidth=0.5)
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.show()
            logger.info(f"第{i}次循环")
            logger.info(f"输入层{sr}个,隐含层{yh}个")

    logger.info(f"最佳输入: {best_sr}")
    logger.info(f"最佳隐含层: {best_yh}")
    logger.info(f"最佳MAPE: {min_mape}")
    return col.tolist(), float(min_mape)
