"""随机森林预测算法模块

本模块实现了基于随机森林的时间序列预测算法，
用于预测备件需求。
"""

import csv
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

# 导入数据预处理函数
sys.path.append(str(Path(__file__).parent.parent))
from data_processor import preprocess_try

logger = logging.getLogger(__name__)


# 随机森林预测
def forest_try(n: int) -> tuple[float, pd.Index]:
    # 读取数据
    df = preprocess_try()

    col = df.columns

    # %%
    df = df.iloc[:, [0, n]]
    df.columns = ["time", "values"]

    #
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

    # print(X_train,y_train)
    # 创建和训练随机森林模型

    # 设置要尝试的参数值列表
    # n_estimators_list = [5,20,40,60,80, 100, 120]
    # max_depth_list = [10,20, 40, 60,80,100]

    n_estimators_list = np.arange(5, 100, 5)
    max_depth_list = np.arange(5, 100, 5)

    # 初始化最小 MAPE 和对应的参数组合
    min_mape = float("inf")
    best_n_estimators = None
    best_max_depth = None
    best_predicted = None
    # 循环尝试不同的参数组合
    for n_estimators in n_estimators_list:
        for max_depth in max_depth_list:
            # 创建和训练随机森林模型
            rf_model = RandomForestRegressor(n_estimators=n_estimators, random_state=0, max_depth=max_depth)
            rf_model.fit(X_train, y_train)
            # 在测试集上评估模型性能
            y_pred = rf_model.predict(X_test)
            mape = np.mean(np.abs((y_pred - y_test) / y_test))

            # 更新最小 MAPE 和对应的参数组合
            if mape < min_mape:
                min_mape = mape
                best_n_estimators = n_estimators
                best_max_depth = max_depth
                best_predicted = y_pred
                # 记录参数组合和性能
            logger.debug(
                "n_estimators=%d, max_depth=%d, MAPE=%f, Best_predicted=%s", n_estimators, max_depth, mape, str(y_pred)
            )

    # 记录最佳参数组合和最小的 MAPE
    logger.info(
        "Best parameters: n_estimators=%d, max_depth=%d, Min MAPE=%f, Best_predicted=%s",
        best_n_estimators,
        best_max_depth,
        min_mape,
        str(best_predicted),
    )

    # # 预测未来3个月的销售额
    # next_months = pd.date_range(start=data.index[-1], periods=3, freq='M')
    # next_months_data = pd.DataFrame({'Month': next_months.month}, index=next_months)
    # predicted_sales = rf_model.predict(next_months_data[['Month']])

    # 打印预测结果
    # print("预测未来3个月的需求：")
    # print(predicted_sales)

    # 计算模型性能
    # y_pred = rf_model.predict(X_test)
    # mape = np.mean(np.abs((y_pred - y_test) / y_test))
    logger.info("MAPE: %f", min_mape)
    # mae = mean_absolute_error(y_test, y_pred)

    # 将预测结果与真实数据绘制成图表
    # 在绘图前指定字体
    # plt.rcParams["font.family"] = "SimHei"  # 使用宋体字体
    # plt.rcParams["font.size"] = 12  # 设置字体大小
    _, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["time"], df["values"], label="真实数量", color="black")
    last_five_time = df["time"].tail(4)
    if best_predicted is not None:
        ax.plot(last_five_time, best_predicted, label="预测数量", color="r")

    # ax.plot(next_months, predicted_sales, label='未来3个月预测', color='g')

    # 其他绘图设置
    plt.xlabel("日期")
    plt.ylabel("数量")
    plt.title(f"物料号：{col[n]} \n MAPE:{round(min_mape, 2)}")

    plt.legend()
    # plt.grid(True)
    plt.xticks(rotation=45)  # 如果需要旋转刻度标签
    plt.tight_layout()  # 确保标签不重叠
    plt.grid(grid=True, linestyle="--", linewidth=0.5)
    plt.tight_layout()
    plt.savefig("FST")
    plt.show()
    return float(min_mape), col


def fst_run() -> None:
    """运行随机森林预测并保存结果"""
    # 创建一个空列表，用于存储 MAPE 值
    fst_mape_values = []
    for n in data_fst:
        # 运行 SMAforecast_try() 并计算 MAPE
        min_mape, col = forest_try(n)
        # 取出对应的物料号
        material_number = col[n]
        logger.info("物料号: %s", material_number)
        logger.info("MAPE: %f", min_mape)
        # 将 MAPE 值作为元组添加到列表中
        fst_mape_values.append((material_number, min_mape))
    # 将 MAPE 值写入文件
    output_path = Path("FST不平稳杭宁.txt")
    with output_path.open("w", encoding="utf-8") as f:
        # 循环遍历每个 n 对应的 MAPE 值，并将其写入文件
        for material_number, min_mape in fst_mape_values:
            f.write(f"物料号：{material_number}, MAPE FSR: {round(min_mape, 2)}\n")
    csv_filename = "FST不平稳杭宁.csv"
    csv_path = Path(csv_filename)
    with csv_path.open("a", newline="", encoding="utf-8") as f:  # 使用追加模式，并且指定 newline='' 来避免空行
        writer = csv.writer(f)
        # 循环遍历每个 n 对应的 MAPE 值，并将其写入文件
        for material_number, min_mape in fst_mape_values:
            writer.writerow([material_number, round(min_mape, 2)])

    plt.show()
    return


if __name__ == "__main__":
    # 物料取值
    data_fst = range(1, 2)
    # 运行
    fst_run()
