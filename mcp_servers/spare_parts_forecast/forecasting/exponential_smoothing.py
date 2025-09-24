"""
指数平滑预测(一次、二次、三次) - 基于原始notebook实现
"""
import itertools
import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

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


# 指数平滑预测(一、二、三)
def ema_forecast_try(n: int) -> tuple[float, float, float, pd.Index, float, float, float, float, float, float]:
    """
    运行指数平滑预测(一次、二次、三次)
    
    Args:
        n: 物料列索引
        
    Returns:
        tuple: (best_mape_one, best_mape_two, best_mape_three, col,
                best_alpha_d, best_beta_d, best_alpha_t, best_beta_t,
                best_gamma_t, best_season_periods)
    """
    # 数据预处理
    df = preprocess_try()
    # 读取列索引名
    col = df.columns
    # 转换为日期时间索引
    df = df.set_index("time")
    # 划分训练和测试
    train = df[:"2022 第2季度"]
    test = df["2022 第3季度":]
    train = train.iloc[:, n - 1]
    train = train.astype(float)
    test = test.iloc[:, n - 1]
    test = test.astype(float)

    # 定义一个指数平滑模型的超参数优化函数
    # 遍历不同的 alpha 值，通过拟合一次指数平滑模型到训练数据，并在测试集上计算 MAE，找到最佳的 alpha 值，
    # 然后返回最佳的 alpha 值和对应的 MAE 值。这样可以帮助选择在指数平滑模型中的最佳超参数，以获得最佳的预测性能。
    def ses_optimizer(
        train: pd.Series, alphas: np.ndarray, step: int = 4
    ) -> tuple[float, float]:  # step for length of test set
        # 初始化最佳的 alpha 值和最佳的 MAPE 为无穷大
        best_alpha: float = 0.1
        best_mape_one = float("inf")
        # 遍历 alpha 值的候选列表
        for alpha in alphas:
            # 使用当前的 alpha 值拟合一次指数平滑模型到训练数据
            ses_model = SimpleExpSmoothing(train).fit(smoothing_level=alpha)
            # 使用拟合的模型预测未来 step 个时间点的值
            y_pred = ses_model.forecast(step)
            # 计算预测值与测试集的平均绝对误差（MAPE）
            mape_one = np.mean(np.abs((y_pred.to_numpy() - test.to_numpy()) / test.to_numpy()))
            # 如果当前 alpha 值的 MAPE小于最佳 MAPE，则更新最佳 alpha 值和最佳 MAPE
            if mape_one < best_mape_one:
                best_alpha, best_mape_one = alpha, mape_one
            # 记录当前 alpha 值和对应的 MAPE 值
            logging.debug(f"alpha: {round(alpha, 2)}, mape: {round(mape_one, 4)}")
        # 记录最佳的 alpha 值和对应的最佳 MAPE 值
        logging.info(f"best_alpha: {round(best_alpha, 2)}, best_mape_one: {round(best_mape_one, 4)}")
        # 返回最佳的 alpha 值和最佳的 MAPE值
        return best_alpha, best_mape_one

    # 定义一个二次指数平滑模型的超参数优化函数
    # 用于选择最佳的 alpha 和 beta 参数
    def des_optimizer(
        train: pd.Series, alphas: np.ndarray, betas: np.ndarray, step: int = 4
    ) -> tuple[float, float, float]:
        best_alpha: float = 0.1
        best_beta: float = 0.1
        best_mape_two = float("inf")
        # 初始化最佳参数和最佳MAPE
        for alpha in alphas:  # 遍历alpha参数列表
            for beta in betas:  # 遍历beta参数列表
                # 使用ExponentialSmoothing模型拟合训练数据，设置趋势为"add"，并指定alpha和beta参数
                des_model = ExponentialSmoothing(train, trend="add").fit(
                    smoothing_level=alpha, smoothing_trend=beta
                )
                y_pred = des_model.forecast(step)  # 预测未来step个时间步长的值
                # 计算预测值与测试集的平均绝对误差（MAPE）
                mape_two = np.mean(np.abs((y_pred.to_numpy() - test.to_numpy()) / test.to_numpy()))
                if mape_two < best_mape_two:  # 如果当前MAPE更好（更小），则更新最佳参数和最佳MAPE
                    best_alpha, best_beta, best_mape_two = alpha, beta, mape_two
                # 记录当前参数组合的结果
                logging.debug(f"alpha: {round(alpha, 2)}, beta: {round(beta, 2)}, mape: {round(mape_two, 4)}")
        # 记录最佳参数和对应的最佳MAE
        logging.info(
            f"best_alpha: {round(best_alpha, 2)}, "
            f"best_beta: {round(best_beta, 2)}, "
            f"best_mape: {round(best_mape_two, 4)}"
        )
        return best_alpha, best_beta, best_mape_two  # 返回最佳参数和最佳MAPE

    # 定义一个三次指数平滑模型的超参数优化函数
    # 用于选择最佳的 alpha、beta、gamma 参数
    def tes_optimizer(
        train: pd.Series, abg: list, step: int = 4
    ) -> tuple[float, float, float, float, float]:
        # 初始化最佳的 alpha、beta、gamma 和最佳 MAPE
        best_alpha: float = 0.1
        best_beta: float = 0.1
        best_gamma: float = 0.1
        best_mape_three = float("inf")
        best_season_periods = 4.0
        # 遍历参数组合列表
        for comb in abg:
            # 使用给定的参数组合构建三次指数平滑模型-加法模型
            tes_model = ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=comb[3]).fit(
                smoothing_level=comb[0], smoothing_trend=comb[1], smoothing_seasonal=comb[2]
            )
            # 使用模型预测未来的时间点
            y_pred = tes_model.forecast(step)
            mape_three = np.mean(np.abs((y_pred.to_numpy() - test.to_numpy()) / test.to_numpy()))

            # 如果当前 MAPE 更好（更小），则更新最佳参数和最佳 MAPE
            if mape_three < best_mape_three:
                best_alpha, best_beta, best_gamma, best_season_periods, best_mape_three = (
                    comb[0],
                    comb[1],
                    comb[2],
                    comb[3],
                    mape_three,
                )
            # 记录当前参数组合的结果
            logging.debug(
                f"alpha: {round(comb[0], 2)}, beta: {round(comb[1], 2)}, "
                f"gamma: {round(comb[2], 2)}, season: {round(comb[3], 2)}, "
                f"mape: {round(mape_three, 2)}"
            )
        # 记录最佳参数和对应的最佳 MAE
        logging.info(
            f"best_alpha: {round(best_alpha, 2)}, best_beta: {round(best_beta, 2)}, "
            f"best_gamma: {round(best_gamma, 2)}, best_season: {round(best_season_periods)}, "
            f"best_mape: {round(best_mape_three, 4)}"
        )
        # 返回最佳的 alpha、beta、gamma 和最佳 MAPE
        return best_alpha, best_beta, best_gamma, best_season_periods, best_mape_three

    # 一次指数；包含了一系列从0.1到1.0的数字，间隔为0.1（更精确可选间隔为0.01）
    alphas = np.arange(0.10, 1, 0.10)
    # 二次指数
    alphas_d = np.arange(0.10, 1, 0.10)
    betas_d = np.arange(0.10, 1, 0.10)
    # 三次指数   保存最优的参数值，寻找规律，缩小范围，寻找对应参数的普适性；找找最优参数的规律，比如：某个区间
    alphas_t = betas_t = gammas_t = np.arange(0.10, 1, 0.10)
    # 季节性周期
    season_t = np.arange(2, 7, 1)
    abg = list(itertools.product(alphas_t, betas_t, gammas_t, season_t))

    # 保存值
    best_alpha, best_mape_one = ses_optimizer(train, alphas)
    best_alpha_d, best_beta_d, best_mape_two = des_optimizer(train, alphas_d, betas_d)
    best_alpha_t, best_beta_t, best_gamma_t, best_season_periods, best_mape_three = tes_optimizer(train, abg)

    # 一次指数平滑
    ses_model = SimpleExpSmoothing(train).fit(smoothing_level=best_alpha)
    # 二次指数平滑
    des_model = ExponentialSmoothing(train, trend="add").fit(smoothing_level=best_alpha_d, smoothing_trend=best_beta_d)
    # 三次指数平滑Holt-Winters
    tes_model = ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=best_season_periods).fit(
        smoothing_level=best_alpha_t, smoothing_trend=best_beta_t, smoothing_seasonal=best_gamma_t
    )

    # 4个预测值
    y_pred = ses_model.forecast(4)
    y_pred_d = des_model.forecast(4)
    y_pred_t = tes_model.forecast(4)
    logging.info(f"真实值：{test.to_numpy()}")
    logging.info(f"三次预测值：{y_pred_t}")

    # 作图
    def plot_forecast(train: pd.Series, test: pd.Series, y_pred: pd.Series, title: str) -> None:
        mape = np.mean(np.abs((y_pred.to_numpy() - test.to_numpy()) / test.to_numpy()))
        plt.figure(figsize=(10, 6))
        # 合并训练和测试数据
        full_data = pd.concat([train, test])
        plt.plot(full_data.index, full_data.to_numpy(), label=" Training Data", color="black")  # 合并后的数据
        plt.plot(test.index, y_pred, label="Forecast", color="red")
        plt.title(f"{df.columns[n - 1]}, {title}, MAPE:{round(mape, 2)}")
        plt.xlabel("Time")
        plt.ylabel("Values")
        plt.xticks(rotation=45)
        plt.grid(visible=True, linestyle="--", linewidth=0.5)
        plt.legend()
        plt.tight_layout()
        plt.savefig(title)
        plt.show()

    plot_forecast(train, test, y_pred, "Single Exponential Smoothing")
    plot_forecast(train, test, y_pred_d, "Double Exponential Smoothing")
    plot_forecast(train, test, y_pred_t, "Triple Exponential Smoothing")
    return (
        best_mape_one,
        best_mape_two,
        best_mape_three,
        col,
        best_alpha_d,
        best_beta_d,
        best_alpha_t,
        best_beta_t,
        best_gamma_t,
        best_season_periods,
    )


# 运行指数平滑法、写入
def ema_run() -> None:
    """运行指数平滑预测的批量处理函数"""
    # 创建一个空列表，用于存储 MAPE 值
    ema_mape_values = []
    for n in data_ema:
        # 运行 ema_forecast_try() 并计算 MAPE
        (
            best_mape_one,
            best_mape_two,
            best_mape_three,
            col,
            best_alpha_d,
            best_beta_d,
            best_alpha_t,
            best_beta_t,
            best_gamma_t,
            best_season_periods,
        ) = ema_forecast_try(n)
        # 取出对应的物料号
        material_number = col[n]
        logging.info(f"这是 {material_number}")
        logging.info(
            f"{best_mape_one}, {best_mape_two}, {best_mape_three}, "
            f"{best_alpha_d}, {best_beta_d}, {best_alpha_t}, {best_beta_t}, "
            f"{best_gamma_t}, {best_season_periods}"
        )
        # 将 MAPE 值作为元组添加到列表中
        ema_mape_values.append(
            (
                material_number,
                best_mape_one,
                best_mape_two,
                best_mape_three,
                best_alpha_d,
                best_beta_d,
                best_alpha_t,
                best_beta_t,
                best_gamma_t,
                best_season_periods,
            )
        )
    # 可选：将结果写入文件 (当前已注释)
    # 可选：将结果写入CSV文件 (当前已注释)
    return


if __name__ == "__main__":
    # 物料取值
    data_ema = range(1, 2)
    # 运行
    ema_run()
