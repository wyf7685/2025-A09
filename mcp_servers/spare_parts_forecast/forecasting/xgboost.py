"""
XGBoost预测模块 - 基于灰狼优化算法的XGBoost回归预测

该模块实现了使用灰狼优化算法优化XGBoost超参数的时间序列预测功能。
主要功能:
- 数据预处理和特征工程
- 灰狼优化算法实现
- XGBoost模型训练和预测
- 模型评估和结果可视化
"""

import logging
import math
import warnings

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import numpy.random as rd
import pandas as pd
import xgboost as xgb
from sklearn.metrics import r2_score

# 配置matplotlib
mpl.use("TkAgg")
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 忽略警告
warnings.filterwarnings("ignore")


# 定义灰狼优化算法实现函数
def sanitized_gwo(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    SearchAgents_no: int,
    T: int,
    dim: int,
    lb: float,
    ub: float,
) -> tuple[float, float, float, list, list]:
    Alpha_position = [0, 0]  # 初始化Alpha灰狼的位置
    Beta_position = [0, 0]  # 初始化Beta灰狼的位置
    Delta_position = [0, 0]  # 初始化Delta灰狼的位置

    Alpha_score = float("inf")  # 初始化Alpha灰狼目标函数的值
    Beta_score = float("inf")  # 初始化Beta灰狼目标函数的值
    Delta_score = float("inf")  # 初始化Delta灰狼目标函数的值

    Positions = np.dot(rd.rand(SearchAgents_no, dim), (ub - lb)) + lb  # 初始化第一个搜索位置

    iterations = []  # 定义迭代次数列表
    accuracy = []  # 定义准确率列表

    # 迭代求解
    t = 0
    while t < T:  # 循环
        # 迭代每只灰狼位置
        for i in range(Positions.shape[0]):
            # 如果搜索位置超出了搜索空间，则需要返回到搜索空间
            for j in range(Positions.shape[1]):
                Flag4ub = Positions[i, j] > ub  # 大于最大值
                Flag4lb = Positions[i, j] < lb  # 小于最小值
                # 如果灰狼的位置在最大值和最小值之间，则不需要调整位置
                # 如果超过最大值，则返回最大值边界；如果低于最小值，则返回最小值边界
                if Flag4ub:  # 判断
                    Positions[i, j] = ub  # 赋值
                if Flag4lb:  # 判断
                    Positions[i, j] = lb  # 赋值

            # 建立XGB模型并训练
            # XGB预测
            model = xgb.XGBRegressor(
                max_depth=int(abs(Positions[i][0])),
                learning_rate=int(abs(Positions[i][1])) * 0.01,
                n_estimators=int(abs(Positions[i][2])) * 100,
                random_state=42,
            )
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            score = round(r2_score(y_test, y_pred), 4)  # 计算R2

            # 使错误率降到最低
            fitness_value = 1 - score  # 错误率 赋值 适应度函数值
            if fitness_value < Alpha_score:  # 如果目标函数值小于Alpha灰狼的目标函数值
                Alpha_score = fitness_value  # 然后将Alpha灰狼的目标函数值更新为最优目标函数值
                Alpha_position = Positions[i]  # 同时更新Alpha灰狼的位置到最佳位置
            if (
                fitness_value > Alpha_score and fitness_value < Beta_score
            ):  # 如果目标函数值大于Alpha灰狼的目标函数值并且小于Beta灰狼的目标函数值
                Beta_score = fitness_value  # 然后将Beta灰狼的目标函数值更新为最优目标函数值
                Beta_position = Positions[i]  # 同时更新Beta灰狼的位置到最佳位置
            # 如果目标函数值大于Alpha灰狼的目标函数值并且大于Beta灰狼的目标函数值并且小于Delta灰狼的目标函数值
            if fitness_value > Alpha_score and fitness_value > Beta_score and fitness_value < Delta_score:
                Delta_score = fitness_value  # 然后将Delta灰狼的目标函数值更新为最优目标函数值
                Delta_position = Positions[i]  # 同时更新Delta灰狼的位置到最佳位置

        a = 2 - t * (2 / T)  # 收敛因子从2线性递减到0

        # 循环更新灰狼个体的位置
        for i in range(Positions.shape[0]):
            # 遍历每个维度
            for j in range(Positions.shape[1]):
                # 包围猎物，更新位置
                r1 = rd.random(1)  # 生成0~1之间的随机数
                A1 = 2 * a * r1 - a  # 计算系数向量A
                C1 = 0.5 + (0.5 * math.exp(-j / 500)) + (1.4 * (math.sin(j) / 30))  # 通过时变加速度常数 计算系数向量C

                # alpha灰狼位置更新
                D_alpha = abs(C1 * Alpha_position[j] - Positions[i, j])  # alpha灰狼与其它个体的距离
                X1 = Alpha_position[j] - A1 * D_alpha  # alpha灰狼当前的位置

                r1 = rd.random(1)  # 生成0~1之间的随机数

                A2 = 2 * a * r1 - a  # 计算系数向量A
                C2 = (
                    1 + (1.4 * (1 - math.exp(-j / 500))) + (1.4 * (math.sin(j) / 30))
                )  # 基于差分均值的摄动时变参数 计算系数向量C

                # Beta灰狼位置更新
                D_beta = abs(C2 * Beta_position[j] - Positions[i, j])  # Beta灰狼与其它个体的距离
                X2 = Beta_position[j] - A2 * D_beta  # Beta灰狼当前的位置

                r1 = rd.random(1)  # 生成0~1之间的随机数

                A3 = 2 * a * r1 - a  # 计算系数向量A
                C3 = (1 / (1 + math.exp(-0.0001 * j / T))) + (
                    (0.5 - 2.5) * ((j / T) ** 2)
                )  # 基于sigmoid函数的加速度系数 计算系数向量C

                # Delta灰狼位置更新
                D_delta = abs(C3 * Delta_position[j] - Positions[i, j])  # Delta灰狼与其它个体的距离
                X3 = Delta_position[j] - A3 * D_delta  # Delta灰狼当前的位置

                # 位置更新
                Positions[i, j] = (X1 + X2 + X3) / 3

        t = t + 1
        iterations.append(t)  # 迭代次数存入列表中
        accuracy.append(abs((100 - Alpha_score) / 100))  # 计算准确率
        logger.info(f"迭代次数: {t}")

    best_depth = Alpha_position[0]
    best_lr = Alpha_position[1]  # 最优位置  即最优参数值
    best_estimators = Alpha_position[2]  # 最优位置  即最优参数值

    return best_depth, best_lr, best_estimators, iterations, accuracy  # 返回数据


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


def xgboost_forecast(column_index: int, df: pd.DataFrame) -> dict:
    """
    XGBoost预测主函数

    Args:
        column_index: 数据列索引，默认为16
    """
    # 获取预处理数据
    # df = preprocess_data()

    # 选择指定列
    df = df.iloc[:, [0, column_index]] if len(df.columns) > column_index else df.iloc[:, [0, 1]]
    df.columns = ["time", "values"]

    # 特征工程
    # 解析季度数据为年份和季度
    df["Year"] = df["time"].str.split(" 第").str[0].astype(int)
    df["Quarter"] = df["time"].str.split("第").str[1].str.replace("季度", "").astype(int)

    # 划分数据集
    train_size = int(0.82 * len(df))
    train_data = df.iloc[:train_size]
    test_data = df.iloc[train_size:]

    # 准备特征和目标变量
    X_train = train_data[["Year", "Quarter"]]
    y_train = train_data["values"]
    X_test = test_data[["Year", "Quarter"]]
    y_test = test_data["values"]

    SearchAgents_no = 50  # 灰狼个数
    T = 2  # 最大迭代次数
    dim = 3  # 维度 需要优化三个变量 - depth lr es
    lb = 1  # 最小值限制
    ub = 50  # 最大值限制

    logger.info("调用灰狼算法函数")
    best_depth, best_lr, best_estimators, _, _ = sanitized_gwo(
        X_train, X_test, y_train, y_test, SearchAgents_no, T, dim, lb, ub
    )

    logger.info("最优结果展示")
    logger.info(f"最优深度: {int(abs(best_depth))}")
    logger.info(f"最优学习率: {int(abs(best_lr)) * 0.01}")
    logger.info(f"最优估计器数量: {int(abs(best_estimators)) * 100}")

    logger.info("应用优化后的最优参数值构建XGB回归模型")
    # 建立XGB模型并训练
    model = xgb.XGBRegressor(
        max_depth=int(abs(best_depth)),
        learning_rate=int(abs(best_lr)) * 0.01,
        n_estimators=int(abs(best_estimators)) * 100,
        random_state=42,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mape = np.mean(np.abs((y_pred - y_test) / y_test))

    logger.info("模型评估")
    logger.info("输出测试集的模型评估指标结果")
    logger.info(f"XGB回归模型-最优参数-MAPE：{mape}")

    # 真实值与预测值比对图
    plt.figure(figsize=(12, 6))
    plt.rcParams["font.sans-serif"] = ["SimHei"]  # 用来正常显示中文标签
    plt.rcParams["axes.unicode_minus"] = False  # 用来正常显示负号
    plt.plot(df["time"], df["values"], label="真实数量", color="black")
    last_five_time = df["time"].tail(4)
    plt.plot(last_five_time, y_pred, label="预测数量", color="r")
    plt.legend(["真实值", "预测值"])  # 设置图例
    plt.title("智能灰狼优化算法优化XGB回归模型真实值与预测值比对图")  # 设置标题名称
    plt.show()  # 显示图片

    return {
        "best_depth": int(abs(best_depth)),
        "best_lr": int(abs(best_lr)) * 0.01,
        "best_estimators": int(abs(best_estimators)) * 100,
        "mape": mape,
        "predictions": y_pred.tolist(),
        "actual": y_test.tolist(),
    }
