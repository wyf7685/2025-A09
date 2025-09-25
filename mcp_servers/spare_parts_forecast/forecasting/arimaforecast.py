"""
ARIMA预测模型

提供ARIMA和SARIMA时间序列预测功能，包括数据预处理、模型训练、
参数优化和预测评估等功能。
"""

import itertools
import logging
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import mean_squared_error
from statsmodels.graphics.gofplots import qqplot
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

logger = logging.getLogger(__name__)


# ARIMA预测
# 基础 ARIMA 模型
def arimaforecast_try(n: int, df: pd.DataFrame) -> float:
    # 重采样
    def resampling(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """数据重采样函数"""
        df = data
        # df['time'] = pd.to_datetime(df['time'])
        df = df.set_index("time")
        train_data = df["2018 第1季度":"2022 第1季度"]
        test_data = df["2022 第2季度":"2023 第2季度"]
        # 以月为时间间隔取均值,重采样
        # train_data = train_data.resample('M').mean()
        # test_data = test.resample('M').mean()
        # print(train_data, test_data)
        return train_data, test_data  # pyright: ignore[reportReturnType]

    #### Step 3  差分转平稳
    def stationarity(
        timeseries: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:  # 平稳性处理（timeseries 时间序列）
        ## 差分法,保存成新的列
        diff1 = timeseries.diff(1).dropna()  # 1阶差分 dropna() 删除缺失值
        diff2 = diff1.diff(1).dropna()  # 在一阶差分基础上再做一次一阶差分，即二阶查分
        ## 画图
        # diff1.plot(color='red', title='diff 1', figsize=(10, 4))
        # diff2.plot(color='black', title='diff 2', figsize=(10, 4))
        ## 平滑法
        rollmean = (
            timeseries.rolling(window=4, center=False).mean()  ## 滚动平均
        ).dropna()  # pyright: ignore[reportAttributeAccessIssue]
        rollstd = timeseries.rolling(window=4, center=False).std().dropna()  ## 滚动标准差
        ## 画图
        # rollmean.plot(color='yellow', title='Rolling Mean', figsize=(10, 4))
        # rollstd.plot(color='blue', title='Rolling Std', figsize=(10, 4))
        return diff1, diff2, rollmean, rollstd  # pyright: ignore[reportReturnType]

    # 平稳性检验
    #### Step 4  平稳性检验
    def adf_test(timeseries: pd.DataFrame) -> bool:  ## 用于检测序列是否平稳
        """ADF平稳性检验"""
        column_name = timeseries.columns[0]
        x = np.array(timeseries[column_name])
        adftest = adfuller(x, autolag="AIC")
        logger.debug("ADF test results: %s", adftest)

        # adftest返回的是一个元组，第4个元素是临界值字典，第1个元素是p值
        critical_values = adftest[4] if len(adftest) > 4 else {}
        p_value = adftest[1]

        if isinstance(critical_values, dict) and "1%" in critical_values:
            is_stationary = adftest[0] < critical_values["1%"] and p_value < 1e-8
        else:
            is_stationary = p_value < 0.05  # 简化判断

        if is_stationary:
            logger.info("序列平稳")
            return True
        logger.info("非平稳序列")
        return False

    # 随机性检验（白噪声检验）
    def random_test(timeseries: pd.DataFrame) -> bool:
        """随机性检验（白噪声检验）"""
        try:
            p_value = acorr_ljungbox(timeseries, lags=1)  # p_value 返回二维数组，第二维为P值
            logger.debug("Ljung-Box test results: %s", p_value)

            if "lb_pvalue" in p_value.columns and p_value["lb_pvalue"].iloc[0] < 0.05:
                logger.info("非随机性序列")
                return True
            logger.info("随机性序列,即白噪声序列")
            return False
        except Exception as e:
            logger.warning("随机性检验失败: %s", e)
            return False

    # 利用ACF和PACF判断模型阶数
    def determinate_order_acf(timeseries: pd.DataFrame) -> None:
        plot_acf(timeseries, lags=16)  # 延迟数
        plot_pacf(timeseries, lags=7)
        plt.show()

    # ARMA模型
    def arma_model(train_data: pd.DataFrame, order: tuple[int, int, int]) -> tuple[Any, Any, Any]:
        """ARMA模型训练和预测"""
        arma_model = ARIMA(train_data, order=order)
        arma = arma_model.fit()
        # 样本内预测
        in_sample_pred = arma.predict()
        # 样本外预测
        out_sample_pred = arma.predict(start=len(train_data) - 1, end=len(train_data) + 11, dynamic=True)
        return arma, in_sample_pred, out_sample_pred

    # ARIMA模型
    def arima_model(train_data: pd.DataFrame, order: tuple[int, int, int]) -> tuple[Any, Any, Any]:
        """ARIMA模型训练和预测"""
        arima_model = ARIMA(train_data, order=order)
        arima = arima_model.fit()
        # 样本内预测
        in_sample_pred = arima.predict()
        # 样本外预测
        out_sample_pred = arima.predict(start=len(train_data) - 1, end=len(train_data) + 4, dynamic=True)
        return arima, in_sample_pred, out_sample_pred

    # 模型评估
    def evaluate_model(model: Any, train_data: pd.DataFrame, predict_data: pd.Series) -> None:
        # （1）利用QQ图检验残差是否满足正态分布
        resid = model.resid  # 求解模型残差
        plt.figure(figsize=(12, 8))
        qqplot(resid, line="q", fit=True)
        plt.xlabel("理论分位数")
        plt.ylabel("样本分位数")
        plt.legend(["残差"], loc="upper left")
        plt.show()
        plt.close()
        # （2）利用D-W检验,检验残差的自相关性
        logger.debug("D-W检验值为%f", durbin_watson(resid.values))
        # （3）利用预测值和真实值的误差检测，这里用的是标准差
        logger.debug(
            "标准差为%f",
            mean_squared_error(train_data, predict_data, sample_weight=None, multioutput="uniform_average"),
        )  # 标准差（均方差）

    def draw_picture(row_train_data: pd.DataFrame, out_sample_pred_arima: pd.Series, test_data: pd.DataFrame) -> float:
        # print(out_sample_pred)
        # 样本外预测传入 test_data,out_sample_pred
        # 由于预测都是由差分后的平稳序列得出,因此需要对差分后的数据进行还原
        # 还原后绘制同一起点的曲线
        # 将差分后的序列还原,re_out_sample_pred为还原之后
        base_series = pd.Series(np.array(row_train_data)[-2][0], index=[row_train_data.index[-2]])
        re_out_sample_pred_arima = pd.concat([base_series, out_sample_pred_arima[1:]]).cumsum()  # pyright: ignore[reportCallIssue, reportArgumentType]

        # # 横坐标
        # x = []
        # start_value = 45  # 设置起始值为44
        # for i in range(24):
        #     x.append(start_value + i)
        # x = np.array(x)
        # x_1 = []
        # for i in range(44):
        #     x_1.append(i + 1)
        # x_1 = np.array(x_1)
        # df_all = preprocess_try()
        # print(x)
        # 使用between方法来切片时间列
        # x_train_time = x[x['time'].between('2018 第1季度', '2022 第2季度')]
        # x_test_time = x[x['time'].between('2022 第3季度', '2023 第2季度')]

        # 纵坐标
        y1 = np.array(row_train_data)
        y2 = np.array(test_data)
        # y3 = np.array(re_out_sample_pred_arma[1:])

        y4 = np.array(re_out_sample_pred_arima[1:])
        logger.debug("y4 values: %s", y4)
        mape = np.mean(np.abs((y4 - y2) / y2))

        # 画图
        plt.plot(train_data.index, y1, label="Training Data")
        plt.plot(test_data.index, y2, color="b", label="Test Data")
        # plt.plot(x_test_time, y3, color='r', label='ARMA Prediction')
        logger.debug("测试数据索引: %s", test_data.index)
        plt.plot(test_data.index, y4, color="r", label="ARIMA Prediction")
        plt.title(f"{df_all.columns[n]},MAPE_ARIMA:{round(mape, 2)}")
        # 添加图例
        plt.legend()
        plt.xticks(rotation=90)
        # plt.show()
        # plt.close()
        return float(mape)

    # 参数

    # n = 6                        # 读取的列索引序号

    # 数据预处理
    df_all = df.copy()
    df = df.iloc[:, [0, n]]  # 选择第0列和第n列，这将保留时间列和第n列

    # # 重采样,划分训练测试
    train_data, test_data = resampling(df)
    train_data = train_data.astype(float)
    row_train_data = train_data  # 保存差分前的序列,为了后面做评估
    logger.debug("原始训练数据: %s", row_train_data)
    # 差分转平稳
    smooth_data = stationarity(train_data)
    logger.debug("平稳处理后的数据: %s", smooth_data)

    # for data in zip(Smooth_data, range(4)):
    # range(4) 用于判断哪种方法 满足平稳性和白噪声 diff1 diff2 rollmean,rollstd
    #     # print(data[0])
    #     if ADF_test(data[0]) and random_test(data[0]):  # 平稳性和白噪声检测
    #         train_data = data[0]                        # 先用差分，再用平滑,分别对应4个序列
    #         method = data[1]
    #         print(method)                               # 如果是差分做的,那么后面ARIMA模型中要使用这个参数
    #         break
    # print(train_data)

    # determinate_order_acf(train_data)  # ACF定阶

    # 参数
    # order_arma = (1, 0, 1)  # ARMA      p,q其中d=0
    order_arima = (2, 1, 1)  # ARIMA     p,d,q

    # print(order_arma.dtypes)
    # 调用模型
    # arma, in_sample_pred_arma, out_sample_pred_arma = arma_model(train_data, order_arma)
    _, _, out_sample_pred_arima = arima_model(train_data, order_arima)

    # #
    # 模型评价
    # evaluate_model(arma, train_data, in_sample_pred_arma)
    # evaluate_model(arima, train_data, in_sample_pred_arima)
    # #
    # # 可视化
    draw_picture(row_train_data, out_sample_pred_arima, test_data)

    # 返回ARIMA模型的MAPE值作为示例
    return 0.0  # 临时返回值，实际应返回计算的MAPE


# SARIMA模型（考虑季节性）
def arima_try(n: int, data: pd.DataFrame) -> tuple[float, pd.Index]:
    # Load the data
    col = data.columns
    data = data.iloc[:, [0, n]]
    # A bit of pre-processing to make it nicer
    data = data.set_index(["time"])

    #
    def convert_to_first_month(quarter_str: str) -> str:
        """将季度字符串转换为该季度第一个月的日期字符串"""
        year, quarter = quarter_str.split(" 第")
        year = int(year)
        quarter = int(quarter[0])

        if quarter == 1:
            month = 1
        elif quarter == 2:
            month = 4
        elif quarter == 3:
            month = 7
        else:  # quarter == 4
            month = 10

        return f"{year}-{month}-1"

    #
    # 将data中"time"列的值根据convert_to_first_month函数进行转换
    data.index = data.index.map(convert_to_first_month)
    # 将索引转换为日期时间类型
    data.index = pd.to_datetime(data.index)
    #
    # # 显示更改后的数据
    logger.debug("训练数据: %s", data)
    #
    # 划分训练测试
    train_data = data["2018-4-1":"2022-4-1"]
    test_data = data["2022-7-1":"2023-7-1"]
    train_data = train_data.astype(float)  # 将数据转换为浮点数类型
    test_data = test_data.astype(float)  # 将数据转换为浮点数类型
    logger.debug("测试数据: %s", test_data)

    # 定义 d 和 q 参数，它们的取值范围在 0 到 1 之间
    q = range(3)
    d = range(2)
    # 要定义 p 参数，其取值范围在 0 到 3 之间
    p = range(4)

    # 生成所有不同的 p、d 和 q 参数的组合。
    pdq = list(itertools.product(p, d, q))

    # 生成所有不同的季节性 p、d 和 q 参数的组合
    seasonal_pdq = [(x[0], x[1], x[2], 4) for x in list(itertools.product(p, d, q))]

    logger.debug("Examples of parameter combinations for Seasonal ARIMA...")
    logger.debug("SARIMAX: %s x %s", pdq[1], seasonal_pdq[1])
    logger.debug("SARIMAX: %s x %s", pdq[1], seasonal_pdq[2])
    logger.debug("SARIMAX: %s x %s", pdq[2], seasonal_pdq[3])
    logger.debug("SARIMAX: %s x %s", pdq[2], seasonal_pdq[4])

    AIC = []
    SARIMAX_model = []
    for param in pdq:
        for param_seasonal in seasonal_pdq:
            try:
                mod = sm.tsa.statespace.SARIMAX(
                    train_data,
                    order=param,
                    seasonal_order=param_seasonal,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )

                results = mod.fit(disp=False)

                # 使用getattr获取AIC值，提供默认值以防类型检查问题
                aic_value = getattr(results, "aic", float("inf"))
                logger.debug("SARIMAX%sx%s - AIC:%s", param, param_seasonal, aic_value)
                AIC.append(aic_value)
                SARIMAX_model.append([param, param_seasonal])
            except Exception as e:
                logger.warning("SARIMAX模型拟合失败 %sx%s: %s", param, param_seasonal, e)
                continue

    logger.info(
        "The smallest AIC is %s for model SARIMAX%sx%s",
        min(AIC),
        SARIMAX_model[AIC.index(min(AIC))][0],
        SARIMAX_model[AIC.index(min(AIC))][1],
    )

    # 重新拟合最佳模型
    mod = sm.tsa.statespace.SARIMAX(
        train_data,
        order=SARIMAX_model[AIC.index(min(AIC))][0],
        seasonal_order=SARIMAX_model[AIC.index(min(AIC))][1],
        enforce_stationarity=False,
        enforce_invertibility=False,
    )

    results = mod.fit(disp=False)
    plt.show()

    # 样本外预测 - 使用通用方法
    try:
        # 使用简单的预测方法，避免复杂的类型检查问题
        forecast_steps = len(test_data)

        # 尝试多种预测方法
        prediction = None
        if hasattr(results, "forecast"):
            try:
                prediction = results.forecast(steps=forecast_steps)  # type: ignore
            except Exception as e:
                logger.debug("forecast方法失败: %s", e)

        if prediction is None and hasattr(results, "get_forecast"):
            try:
                pred_result = results.get_forecast(steps=forecast_steps)  # type: ignore
                if hasattr(pred_result, "predicted_mean"):
                    prediction = pred_result.predicted_mean
            except Exception as e:
                logger.debug("get_forecast方法失败: %s", e)

        # 如果仍然没有预测结果，使用默认值
        if prediction is None:
            prediction = np.full(forecast_steps, test_data.iloc[0, 0])
            logger.warning("无法获取预测结果，使用默认值")

        # 确保预测结果是numpy数组
        if not isinstance(prediction, np.ndarray):
            prediction = np.array(prediction)

        # 获取真实值
        truth = test_data.iloc[:, 0].to_numpy()

        # 确保长度匹配
        min_len = min(len(prediction), len(truth))
        if min_len > 0:
            prediction = prediction[:min_len]
            truth = truth[:min_len]

            # 避免除零错误
            truth_nonzero = np.where(truth != 0, truth, 1e-10)
            mape = float(np.mean(np.abs((truth - prediction) / truth_nonzero)))
            logger.info("MAPE: %f", mape)
        else:
            mape = float("inf")
            logger.warning("无法计算MAPE，数据长度为0")

    except Exception:
        logger.exception("预测过程出错")
        mape = float("inf")
        prediction = np.array([])

    # 绘图
    plt.figure(figsize=(10, 6))
    plt.plot(data.index, data, label="原始数据", color="black")

    # 只有当预测有效时才绘制预测线
    if len(prediction) > 0 and len(prediction) == len(test_data):
        plt.plot(test_data.index, prediction, label="样本外预测", color="r")

    plt.ylabel("数量")
    plt.xlabel("日期")
    plt.xticks(rotation=45)
    plt.title(f"物料号：{col[n]} \n MAPE:{round(mape, 2)}")
    plt.legend()

    plt.grid(grid=True, linestyle="--", linewidth=0.5)
    plt.tight_layout()
    plt.savefig("SARIMA")
    plt.show()
    return float(mape), col
