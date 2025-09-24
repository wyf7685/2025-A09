"""
简单移动平均法预测 - 基于原始notebook实现
"""
import csv
import logging
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 导入数据预处理函数
try:
    from ..data_processor import preprocess_try
except ImportError:
    # 如果没有找到预处理函数，提供一个简单的替代实现
    def preprocess_try() -> pd.DataFrame:
        # 创建示例数据用于测试
        dates = [f"2018 第{i // 4 + 1}季度" if i < 16 else f"2022 第{(i - 16) // 4 + 1}季度" for i in range(22)]
        data = {
            "time": dates,
            "物料号1": np.random.poisson(2, 22),
            "物料号2": np.random.poisson(1.5, 22),
        }
        return pd.DataFrame(data)


def sma_forecast_try(n: int) -> Tuple[float, float, pd.Index]:
    # 参数
    # n = 6               # 读取的列索引序号
    window_size = 3  # 窗口期

    # 数据预处理
    df = preprocess_try()
    # print(df.columns)
    # 读取列索引名
    col = df.columns

    # print(df.iloc[:,n])
    # # 计算移动平均值
    y = df.iloc[:, n].rolling(window=window_size).mean()
    # y_2 = df.iloc[:, n].ewm(span=window_size).mean()
    # 使用rolling窗口并应用自定义权重

    # # 定义自定义权重
    # custom_weights = [0.1, 0.3, 0.6]
    # y_2 = df.iloc[:, n].rolling(window=window_size).apply(
    #     lambda x: (x * custom_weights).sum())

    # 定义一组待尝试的权重组合
    weight_combinations = [
        [0.1, 0.3, 0.6],
        [0.2, 0.3, 0.5],
        [0.2, 0.4, 0.4],
        [0.3, 0.3, 0.4],
        [0.1, 0.4, 0.5],
        [0.1, 0.2, 0.7],
        # 可以添加更多的组合
    ]

    mape_wight = float("inf")  # 初始化最佳 MAPE 为无穷大
    best_weights = None  # 初始化最佳权重组合为空
    y_2_predict = None
    for weights in weight_combinations:
        # 使用当前权重组合计算移动加权平均
        y_2 = df.iloc[:, n].rolling(window=window_size).apply(lambda x, w=weights: (x * w).sum())
        # 计算 MAPE
        y_2_values = y_2[2:-1].to_numpy()
        actual_values = df.iloc[3:, n].to_numpy()
        mape_wight_2 = np.mean(np.abs((y_2_values - actual_values) / actual_values))
        # 更新最佳 MAPE 和对应的权重组合
        if mape_wight_2 < mape_wight:
            mape_wight = mape_wight_2
            best_weights = weights
            y_2_predict = y_2
    logging.info(f"最佳权重组合: {best_weights}")
    logging.info(f"最佳 MAPE: {mape_wight}")
    logging.debug(f"最佳 加权预测值: {y_2_predict}")

    # MAPE
    y_values = y[2:-1].to_numpy()
    actual_values = df.iloc[3:, n].to_numpy()
    mape_single = np.mean(np.abs((y_values - actual_values) / actual_values))
    # mape_wight = np.mean(np.abs((y_2[2:-1].values - df.iloc[3:, n].values) / df.iloc[3:, n].values))
    # mae_single = mean_absolute_error(df.iloc[3:, n].values, y[2:-1].values)
    # mae_wight = mean_absolute_error(df.iloc[3:, n].values, y_2[2:-1].values)

    # print('预测值', y[2:-1].values, '加权',y_2_predict[2:-1].values)
    # print('真实值', df.iloc[3:, n].values)
    # print(y[2:-1].values - df.iloc[3:, n].values)
    logging.info(f"mape单次: {mape_single}")
    logging.info(f"mape加权: {mape_wight}")

    # print(df['time'])

    time_values = df["time"].to_numpy()
    plt.figure(figsize=(10, 6))
    plt.plot(df["time"], df.iloc[:, n], label="原始数据", color="black")
    
    # 确保 y_2_predict 不是 None
    if y_2_predict is not None:
        plt.plot(time_values[1:], y[:-1].to_numpy(), label=f"一次 ({window_size}天)", color="b")
        plt.plot(time_values[1:], y_2_predict[:-1].to_numpy(), label=f"加权 ({window_size}天)", color="r")
    else:
        plt.plot(time_values[1:], y[:-1].to_numpy(), label=f"一次 ({window_size}天)", color="b")
    
    plt.xlabel("日期")
    plt.ylabel("数值")
    # 标题分行显示以符合长度限制
    title_line1 = f"物料号：{col[n]}"
    title_line2 = f"一次移动平均 MAPE:{round(mape_single, 2)}"
    title_line3 = f"加权移动平均法 MAPE:{round(mape_wight, 2)}"
    plt.title(f"{title_line1}\n{title_line2}\n{title_line3}")
    plt.legend()
    plt.xticks(rotation=45)
    plt.grid(visible=True, linestyle="--", linewidth=0.5)
    plt.tight_layout()
    plt.savefig("SMA")
    plt.show()

    return float(mape_single), float(mape_wight), col


def sma_run() -> None:
    # 创建一个空列表，用于存储 MAPE 值
    sma_mape_values = []
    for n in data_sma:
        # 运行 sma_forecast_try() 并计算 MAPE
        mape_single, mape_wight, col = sma_forecast_try(n)
        # 取出对应的物料号
        material_number = col[n]
        # 将 MAPE 值作为元组添加到列表中
        sma_mape_values.append((col[n], mape_single, mape_wight))
    # 将 MAPE 值写入文件
    output_file = Path("SMA不平稳杭宁.txt")
    with output_file.open("w", encoding="utf-8") as f:
        # 循环遍历每个 n 对应的 MAPE 值，并将其写入文件
        for material_number, mape_single, mape_wight in sma_mape_values:
            line = (f"物料号：{material_number}, MAPE Single: {round(mape_single, 2)}, "
                   f"MAPE Weight: {round(mape_wight, 2)}\n")
            f.write(line)
    csv_filename = Path("SMA不平稳杭宁.csv")
    with csv_filename.open("a", newline="", encoding="utf-8") as f:  
        # 使用追加模式，并且指定 newline='' 来避免空行
        writer = csv.writer(f)
        # 循环遍历每个 n 对应的 MAPE 值，并将其写入文件
        for material_number, mape_single, mape_wight in sma_mape_values:
            writer.writerow([material_number, round(mape_single, 2), round(mape_wight, 2)])
    plt.show()


if __name__ == "__main__":
    # 物料取值
    data_sma = range(1, 2)
    # 运行
    sma_run()
