"""
Croston方法及其变体用于间歇性需求预测 - 基于原始notebook实现
"""
import csv
import logging
from pathlib import Path

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


# croston预测
def croston_forecast_try(n: int) -> tuple[float, float, float, pd.Index]:
    """
    运行Croston方法及其变体进行预测
    
    Args:
        n: 物料列索引
        
    Returns:
        tuple: (best_mape_cst, best_mape_sba, best_mape_tsb, col)
    """
    # croston
    def croston(ts: pd.Series, alpha: float, extra_periods: int = 1) -> pd.DataFrame:
        # 将输入数据转换为NumPy数组
        d = np.array(ts)
        # 获取历史期间的长度
        cols = len(d)
        # 在需求数组中附加np.nan，以覆盖未来期间
        d = np.append(d, [np.nan] * extra_periods)

        # 初始化水平（a）、周期性（p）和预测（f）
        a, p, f = np.full((3, cols + extra_periods), np.nan)
        q = 1  # 自上次需求观察以来的期数

        # 初始化
        # 找到第一个需求观察值的位置
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
        a[cols + 1 : cols + extra_periods] = a[cols]
        p[cols + 1 : cols + extra_periods] = p[cols]
        f[cols + 1 : cols + extra_periods] = f[cols]

        # 创建一个包含需求、预测、周期、水平和误差的Pandas DataFrame
        return pd.DataFrame.from_dict({"Demand": d, "Forecast": f, "Period": p, "Level": a, "Error": d - f})

    # croston_sba
    def croston_sba(ts: pd.Series, alpha: float, extra_periods: int = 1) -> pd.DataFrame:
        # 将输入数据转换为NumPy数组
        d = np.array(ts)
        # 获取历史期间的长度
        cols = len(d)
        # 在需求数组中附加np.nan，以覆盖未来期间
        d = np.append(d, [np.nan] * extra_periods)

        # 初始化水平（a）、周期性（p）和预测（f）
        a, p, f = np.full((3, cols + extra_periods), np.nan)
        q = 1  # 自上次需求观察以来的期数

        # 初始化
        # 找到第一个需求观察值的位置
        first_occurrence = np.argmax(d[:cols] > 0)
        a[0] = d[first_occurrence]
        p[0] = 1 + first_occurrence
        f[0] = a[0] / p[0]

        # 创建所有t+1时刻的预测
        for t in range(cols):
            if d[t] > 0:
                a[t + 1] = alpha * d[t] + (1 - alpha) * a[t]
                p[t + 1] = alpha * q + (1 - alpha) * p[t]
                f[t + 1] = (1 - alpha / (2)) * (a[t + 1] / p[t + 1])
                q = 1
            else:
                a[t + 1] = a[t]
                p[t + 1] = p[t]
                f[t + 1] = f[t]
                q += 1

        # 预测未来期间
        a[cols + 1 : cols + extra_periods] = a[cols]
        p[cols + 1 : cols + extra_periods] = p[cols]
        f[cols + 1 : cols + extra_periods] = f[cols]

        # 创建一个包含需求、预测、周期、水平和误差的Pandas DataFrame
        return pd.DataFrame.from_dict({"Demand": d, "Forecast": f, "Period": p, "Level": a, "Error": d - f})

    # croston_tsb
    def croston_tsb(ts: pd.Series, alpha: float, beta: float, extra_periods: int = 1) -> pd.DataFrame:
        d = np.array(ts)  # Transform the input into a numpy array
        cols = len(d)  # Historical period length
        d = np.append(d, [np.nan] * extra_periods)  # Append np.nan into the demand array to cover future periods

        # Level (a), probability (p), and forecast (f)
        a, p, f = np.full((3, cols + extra_periods), np.nan)

        # Initialization
        first_occurrence = np.argmax(d[:cols] > 0)
        a[0] = d[first_occurrence]
        p[0] = 1 / (1 + first_occurrence)
        f[0] = p[0] * a[0]

        # Create all the t+1 forecasts
        for t in range(cols):
            if d[t] > 0:
                a[t + 1] = alpha * d[t] + (1 - alpha) * a[t]
                p[t + 1] = beta * (1) + (1 - beta) * p[t]
            else:
                a[t + 1] = a[t]
                p[t + 1] = (1 - beta) * p[t]
            f[t + 1] = p[t + 1] * a[t + 1]

        # Future Forecast
        a[cols + 1 : cols + extra_periods] = a[cols]
        p[cols + 1 : cols + extra_periods] = p[cols]
        f[cols + 1 : cols + extra_periods] = f[cols]

        return pd.DataFrame.from_dict({"Demand": d, "Forecast": f, "Period": p, "Level": a, "Error": d - f})

    # croston参数迭代
    def cst_optimizer(data: pd.Series) -> tuple[float, float]:
        best_mape_cst = 999.0
        best_alpha_cst = 0.1  # 初始化变量
        # best_mae_cst = 999
        alphas = np.arange(0, 1, 0.1)
        i = 0
        for alpha in alphas:
            i = i + 1
            result_cr = croston(data, float(alpha))
            forecast_cst = result_cr["Forecast"]

            mape_cst = np.mean(np.abs((forecast_cst[:-1].to_numpy() - data.to_numpy()) / data.to_numpy()))
            # mae_cst = mean_absolute_error(data.values, forecast_cst[:-1].values)
            if mape_cst < best_mape_cst:
                best_alpha_cst, best_mape_cst = float(alpha), float(mape_cst)
            logging.debug(f"cst第{i}次迭代")
            logging.debug(f"alpha: {round(alpha, 2)}, mape: {round(mape_cst, 4)}")
            # print("alpha:", round(alpha, 2), "mae:", round(mae_cst, 4))
        # 打印最佳的 alpha 值和对应的最佳 MAE 值
        logging.info(f"best_alpha: {round(best_alpha_cst, 2)}, best_mape: {round(best_mape_cst, 4)}")
        # print("best_alpha:", round(best_alpha_cst, 2), "best_mae:",round(best_mae_cst, 4))
        # 返回最佳的 alpha 值和最佳的 MAE 值
        return best_alpha_cst, best_mape_cst

    # SBA参数迭代
    def sba_optimizer(data: pd.Series) -> tuple[float, float]:
        best_mape_sba = 999.0
        best_alpha_sba = 0.1  # 初始化变量
        # best_mae_sba = 999
        alphas = np.arange(0, 1, 0.1)
        i = 0
        for alpha in alphas:
            i = i + 1
            result_sba = croston_sba(data, float(alpha))
            forecast_sba = result_sba["Forecast"]

            mape_sba = np.mean(np.abs((forecast_sba[:-1].to_numpy() - data.to_numpy()) / data.to_numpy()))
            # mae_sba = mean_absolute_error(data.values, forecast_sba[:-1].values)

            if mape_sba < best_mape_sba:
                best_alpha_sba, best_mape_sba = float(alpha), float(mape_sba)
            logging.debug(f"sba第{i}次迭代")
            logging.debug(f"alpha: {round(alpha, 2)}, mape: {round(mape_sba, 4)}")
            # print("alpha:", round(alpha, 2), "mae:", round(mae_sba, 4))
        # 打印最佳的 alpha 值和对应的最佳 MAE 值
        logging.info(f"best_alpha: {round(best_alpha_sba, 2)}, best_mape: {round(best_mape_sba, 4)}")
        # print("best_alpha:", round(best_alpha_sba, 2), "best_mae:",round(best_mae_sba, 4))
        # 返回最佳的 alpha 值和最佳的 MAE 值
        return best_alpha_sba, best_mape_sba

    # TSB参数优化
    def tsb_optimizer(data: pd.Series) -> tuple[float, float, float]:
        best_mape_tsb = 999.0
        best_alpha_tsb = 0.1
        best_beta_tsb = 0.1
        # best_mae_tsb = 999
        alphas = np.arange(0, 1, 0.1)
        betas = np.arange(0, 1, 0.1)

        i = 0
        for beta in betas:
            for alpha in alphas:
                i = i + 1
                result_tsb = croston_tsb(data, float(alpha), float(beta))
                forecast_tsb = result_tsb["Forecast"]

                mape_tsb = np.mean(np.abs((forecast_tsb[:-1].to_numpy() - data.to_numpy()) / data.to_numpy()))
                # mae_tsb = mean_absolute_error(data.values, forecast_tsb[:-1].values)
                if mape_tsb < best_mape_tsb:
                    best_alpha_tsb, best_beta_tsb, best_mape_tsb = float(alpha), float(beta), float(mape_tsb)
                logging.debug(f"tsb第{i}次迭代")
                logging.debug(f"alpha: {round(alpha, 2)}, beta: {round(beta, 2)}, mape: {round(mape_tsb, 4)}")
            # 打印最佳的 alpha 值和对应的最佳 MAE 值
            logging.info(
                f"best_alpha: {round(best_alpha_tsb, 2)}, "
                f"best_beta: {round(best_beta_tsb, 2)}, "
                f"best_mape: {round(best_mape_tsb, 4)}"
            )
            # 返回最佳的 alpha 值和最佳的 MAE 值
        return best_alpha_tsb, best_beta_tsb, best_mape_tsb

    # 调用
    df = preprocess_try()
    # df = preprocess()
    data = df.iloc[:, n]

    # 读取列索引名
    col = df.columns

    # 数据集分割注释（如果将来需要可以取消注释）
    # train_size = int(0.8 * len(data))
    # train_data = data.iloc[:train_size]  # 未使用
    # test_data = data.iloc[train_size:]   # 未使用

    # 保存最优值
    best_alpha_cst, best_mape_cst = cst_optimizer(data)
    best_alpha_sba, best_mape_sba = sba_optimizer(data)
    best_alpha_tsb, best_beta_tsb, best_mape_tsb = tsb_optimizer(data)
    logging.info(f"CR输入: {best_alpha_cst}, {best_mape_cst}")
    logging.info(f"SBA输入: {best_alpha_sba}, {best_mape_sba}")
    logging.info(f"TSB输入: {best_alpha_tsb}, {best_beta_tsb}, {best_mape_tsb}")
    # 获取预测值
    result_cr = croston(data, best_alpha_cst)
    result_sba = croston_sba(data, best_alpha_sba)
    result_tsb = croston_tsb(data, best_alpha_tsb, best_beta_tsb)
    logging.debug(f"CR: {result_cr}")
    logging.debug(f"SBA: {result_sba}")
    logging.debug(f"TSB: {result_tsb}")
    forecast_cst = result_cr["Forecast"]
    forecast_sba = result_sba["Forecast"]
    forecast_tsb = result_tsb["Forecast"]

    # 画图
    plt.figure(figsize=(10, 6))
    plt.plot(df["time"], data, label="实际数据", color="black")
    plt.plot(df["time"], forecast_cst[:-1], label="预测数据—CR", color="g")
    plt.plot(df["time"], forecast_tsb[:-1], label="预测数据—TSB", color="r")
    plt.plot(df["time"], forecast_sba[:-1], label="预测数据—SBA", color="b")
    plt.xlabel("时间")
    plt.ylabel("需求")
    title = (
        f"物料号：{col[n]}\n"
        f"CST MAPE:{round(best_mape_cst, 2)}\n"
        f"SBA MAPE:{round(best_mape_sba, 2)}\n"
        f"TSB MAPE:{round(best_mape_tsb, 2)}"
    )
    plt.title(title)
    plt.legend()
    plt.xticks(rotation=45)
    plt.grid(visible=True, linestyle="--", linewidth=0.5)
    plt.tight_layout()
    plt.savefig("cst")
    # plt.show()
    return best_mape_cst, best_mape_sba, best_mape_tsb, col


# crosotn及其变体
def cro_run() -> None:
    """运行Croston预测的批量处理函数"""
    # 创建一个空列表，用于存储 MAPE 值
    cro_mape_values = []
    for n in data_cro:
        # 运行 croston_forecast_try() 并计算 MAPE
        best_mape_cst, best_mape_sba, best_mape_tsb, col = croston_forecast_try(n)
        # 取出对应的物料号
        material_number = col[n]
        logging.info(f"这是 {material_number}")
        logging.info(f"{best_mape_cst}, {best_mape_sba}, {best_mape_tsb}")
        # 将 MAPE 值作为元组添加到列表中
        cro_mape_values.append((material_number, best_mape_cst, best_mape_sba, best_mape_tsb))
    # 将 MAPE 值写入文件
    output_path = Path("CRO不平稳.txt")
    with output_path.open("w", encoding="utf-8") as f:
        # 循环遍历每个 n 对应的 MAPE 值，并将其写入文件
        for material_number, best_mape_cst, best_mape_sba, best_mape_tsb in cro_mape_values:
            f.write(
                f"物料号：{material_number}, "
                f"MAPE CRO: {round(best_mape_cst, 2)}, "
                f"MAPE SBA: {round(best_mape_sba, 2)}, "
                f"MAPE TSB:{round(best_mape_tsb, 2)}\n"
            )
    csv_filename = "CRO不平稳杭宁.csv"
    csv_path = Path(csv_filename)
    with csv_path.open("a", newline="", encoding="utf-8") as f:  # 使用追加模式，并且指定 newline='' 来避免空行
        writer = csv.writer(f)
        # 循环遍历每个 n 对应的 MAPE 值，并将其写入文件
        for material_number, best_mape_cst, best_mape_sba, best_mape_tsb in cro_mape_values:
            writer.writerow(
                [material_number, round(best_mape_cst, 2), round(best_mape_sba, 2), round(best_mape_tsb, 2)]
            )
    plt.show()
    return


if __name__ == "__main__":
    # 物料取值
    data_cro = range(1, 2)
    # 运行
    cro_run()
