"""
ARIMA预测模型

提供ARIMA和SARIMA时间序列预测功能，包括数据预处理、模型训练、
参数优化和预测评估等功能。
"""

import io
import logging
import time
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

from .analysis_results import ARIMAAnalysisResult

logger = logging.getLogger(__name__)


def arima_forecast_impl(
    df: pd.DataFrame,
    target_column: str,
    time_column: str,
    arima_order: tuple[int, int, int] = (2, 1, 1),
    confidence_level: float = 0.95,
    enable_diagnostics: bool = True,
    column_label: str | None = None,
    plot_title: str | None = None,
) -> tuple[ARIMAAnalysisResult, bytes | None]:
    """
    ARIMA预测函数，包含详细的分析和诊断

    Args:
        df: 输入数据框
        target_column: 目标预测列名
        time_column: 时间列名
        arima_order: ARIMA模型参数(p,d,q),默认为(2,1,1)
        confidence_level: 置信水平,默认为0.95
        enable_diagnostics: 是否启用诊断(结果附加诊断信息和图表),默认为True
        column_label: 图表中列标签(启用诊断时生效),默认为target_column的值
        plot_title: 图表标题(启用诊断时生效),默认为None

    Returns:
        ARIMAAnalysisResult: 详细的分析结果
    """

    start_time = time.time()
    warnings_list = []

    def resampling(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """数据重采样"""
        split_idx = int(len(data) * 0.8)
        train_data = data.iloc[:split_idx]
        test_data = data.iloc[split_idx:]
        return train_data, test_data

    def stationarity_test(timeseries: pd.DataFrame) -> dict[str, Any]:
        """平稳性检验"""
        column_name = timeseries.columns[0]
        x = np.array(timeseries[column_name])

        # ADF检验
        adftest = adfuller(x, autolag="AIC")

        critical_values = adftest[4] if len(adftest) > 4 else {}
        p_value = adftest[1]

        is_stationary = False
        if isinstance(critical_values, dict) and "1%" in critical_values:
            is_stationary = adftest[0] < critical_values["1%"] and p_value < 1e-8
        else:
            is_stationary = p_value < 0.05

        return {
            "adf_statistic": adftest[0],
            "adf_p_value": p_value,
            "critical_values": critical_values,
            "is_stationary": is_stationary,
        }

    def white_noise_test(timeseries: pd.DataFrame) -> dict[str, Any]:
        """白噪声检验"""
        try:
            lb_result = acorr_ljungbox(timeseries, lags=min(10, len(timeseries) // 4))

            if "lb_stat" in lb_result.columns and "lb_pvalue" in lb_result.columns:
                lb_stat = lb_result["lb_stat"].iloc[-1]  # 取最后一个lag的统计量
                lb_pvalue = lb_result["lb_pvalue"].iloc[-1]  # 取最后一个lag的p值
                is_white_noise = lb_pvalue > 0.05  # p值大于0.05表示是白噪声
            else:
                lb_stat = None
                lb_pvalue = None
                is_white_noise = False

            return {"ljung_box_statistic": lb_stat, "ljung_box_p_value": lb_pvalue, "is_white_noise": is_white_noise}
        except Exception as e:
            warnings_list.append(f"白噪声检验失败: {e}")
            return {"ljung_box_statistic": None, "ljung_box_p_value": None, "is_white_noise": False}

    def arima_model(train_data: pd.DataFrame, order: tuple[int, int, int]) -> dict[str, Any]:
        """ARIMA模型"""
        try:
            model = ARIMA(train_data, order=order)
            fitted_model = model.fit()

            # 样本内预测
            in_sample_pred = fitted_model.fittedvalues

            # 样本外预测
            forecast_result = fitted_model.get_forecast(steps=len(test_data))
            out_sample_pred = forecast_result.predicted_mean

            # 置信区间
            conf_int = forecast_result.conf_int(alpha=1 - confidence_level)

            return {
                "model": fitted_model,
                "in_sample_pred": in_sample_pred,
                "out_sample_pred": out_sample_pred,
                "confidence_intervals": {"lower": conf_int.iloc[:, 0].tolist(), "upper": conf_int.iloc[:, 1].tolist()},
                "aic": fitted_model.aic,
                "bic": fitted_model.bic,
                "log_likelihood": fitted_model.llf,
                "convergence": fitted_model.mle_retvals["converged"] if hasattr(fitted_model, "mle_retvals") else True,
                "ar_params": fitted_model.arparams.tolist() if len(fitted_model.arparams) > 0 else [],
                "ma_params": fitted_model.maparams.tolist() if len(fitted_model.maparams) > 0 else [],
            }
        except Exception as e:
            raise RuntimeError(f"ARIMA模型拟合失败: {e}") from e

    def residual_analysis(model: Any) -> dict[str, float]:
        """残差分析"""
        residuals = model.resid

        # 基本统计量
        resid_mean = float(np.mean(residuals))
        resid_std = float(np.std(residuals))

        # Durbin-Watson检验
        dw_stat = durbin_watson(residuals.values)

        # 正态性检验 (Shapiro-Wilk)
        try:
            if len(residuals) <= 5000:  # Shapiro-Wilk测试对样本量有限制
                _, normality_p = stats.shapiro(residuals)
            else:
                # 对于大样本，使用Kolmogorov-Smirnov测试
                _, normality_p = stats.kstest(residuals, "norm")
        except Exception:
            normality_p = np.nan
            warnings_list.append("正态性检验失败")

        return {
            "residual_mean": resid_mean,
            "residual_std": resid_std,
            "durbin_watson_stat": float(dw_stat),
            "residual_normality_p": float(normality_p) if not np.isnan(normality_p) else 0.0,
        }

    def calc_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
        """计算评估指标"""
        # 处理长度不匹配
        min_len = min(len(actual), len(predicted))
        actual = actual[:min_len]
        predicted = predicted[:min_len]

        # 避免除零错误
        actual_nonzero = np.where(actual != 0, actual, 1e-10)

        # 计算各种指标
        mape = float(np.mean(np.abs((actual - predicted) / actual_nonzero)) * 100)
        mae = float(np.mean(np.abs(actual - predicted)))
        mse = float(np.mean((actual - predicted) ** 2))
        rmse = float(np.sqrt(mse))

        # R-squared
        ss_res = np.sum((actual - predicted) ** 2)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        r_squared = float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0

        return {"mape": mape, "mae": mae, "mse": mse, "rmse": rmse, "r_squared": r_squared}

    def create_plots(
        train_data: pd.DataFrame,
        test_data: pd.DataFrame,
        predicted: np.ndarray,
        conf_intervals: dict[str, list[float]] | None,
        residuals: pd.Series,
    ) -> bytes:
        """创建分析图表"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle(plot_title or f"{column_label or target_column} - ARIMA分析结果", fontsize=16)

        # 1. 主预测图
        axes[0, 0].plot(train_data.index, train_data.values, label="训练数据", color="blue")
        axes[0, 0].plot(test_data.index, test_data.values, label="实际值", color="green")
        axes[0, 0].plot(test_data.index, predicted[: len(test_data)], label="预测值", color="red")

        # 添加置信区间
        if conf_intervals:
            axes[0, 0].fill_between(
                test_data.index,
                conf_intervals["lower"][: len(test_data)],
                conf_intervals["upper"][: len(test_data)],
                alpha=0.3,
                color="red",
                label=f"{confidence_level * 100:.0f}%置信区间",
            )

        axes[0, 0].set_title("预测结果")
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)

        # 2. 残差图
        axes[0, 1].plot(residuals.index, residuals.values, "o-", markersize=3)
        axes[0, 1].axhline(y=0, color="red", linestyle="--")
        axes[0, 1].set_title("残差序列")
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 残差QQ图
        stats.probplot(residuals.values, dist="norm", plot=axes[0, 2])
        axes[0, 2].set_title("残差QQ图")
        axes[0, 2].grid(True, alpha=0.3)

        # 4. ACF图
        plot_acf(residuals.dropna(), ax=axes[1, 0], lags=min(20, len(residuals) // 4))
        axes[1, 0].set_title("残差ACF")

        # 5. PACF图
        plot_pacf(residuals.dropna(), ax=axes[1, 1], lags=min(20, len(residuals) // 4))
        axes[1, 1].set_title("残差PACF")

        # 6. 残差直方图
        axes[1, 2].hist(residuals.values, bins=30, density=True, alpha=0.7, color="skyblue")
        # 添加正态分布曲线
        x = np.linspace(residuals.min(), residuals.max(), 100)
        axes[1, 2].plot(x, stats.norm.pdf(x, residuals.mean(), residuals.std()), "r-", label="正态分布")
        axes[1, 2].set_title("残差分布")
        axes[1, 2].legend()
        axes[1, 2].grid(True, alpha=0.3)

        plt.tight_layout()

        with io.BytesIO() as buf:
            plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
            buf.seek(0)
            return buf.read()

    # 主执行逻辑
    try:
        # 数据验证
        if target_column not in df.columns:
            raise ValueError(f"目标列 '{target_column}' 不存在")
        if time_column not in df.columns:
            raise ValueError(f"时间列 '{time_column}' 不存在")
        # 时间列处理
        if not np.issubdtype(df[time_column].dtype, np.datetime64):  # pyright: ignore[reportArgumentType]
            try:
                df[time_column] = pd.to_datetime(df[time_column])
            except Exception as e:
                raise ValueError(f"时间列转换失败: {e}") from e

        # 数据准备
        df_work = df[[time_column, target_column]].copy().dropna()
        df_work = df_work.set_index(time_column)

        # 数据划分
        train_data, test_data = resampling(df_work)
        train_data = train_data.astype(float)

        # 平稳性检验
        stationarity_result = stationarity_test(train_data)

        # 白噪声检验
        white_noise_result = white_noise_test(train_data)

        # 模型拟合
        model_result = arima_model(train_data, arima_order)
        fitted_model = model_result["model"]

        # 残差分析
        if enable_diagnostics:
            residual_result = residual_analysis(fitted_model)
        else:
            residual_result = {
                "residual_mean": 0.0,
                "residual_std": 0.0,
                "durbin_watson_stat": 0.0,
                "residual_normality_p": 0.0,
            }

        # 预测评估
        actual = test_data.iloc[:, 0].to_numpy()
        predicted = model_result["out_sample_pred"].to_numpy()

        metrics = calc_metrics(actual, predicted)

        # 创建图表
        image_bytes = (
            create_plots(train_data, test_data, predicted, model_result["confidence_intervals"], fitted_model.resid)
            if enable_diagnostics
            else None
        )

        # 构建结果对象
        result = ARIMAAnalysisResult(
            # 基本信息
            algorithm_name="ARIMA",
            target_column=target_column,
            arima_order=arima_order,
            # 数据信息
            total_samples=len(df_work),
            train_samples=len(train_data),
            test_samples=len(test_data),
            train_start_date=str(train_data.index[0]),
            train_end_date=str(train_data.index[-1]),
            test_start_date=str(test_data.index[0]),
            test_end_date=str(test_data.index[-1]),
            # 平稳性检验
            adf_statistic=stationarity_result["adf_statistic"],
            adf_p_value=stationarity_result["adf_p_value"],
            is_stationary=stationarity_result["is_stationary"],
            critical_values=stationarity_result["critical_values"],
            # 白噪声检验
            ljung_box_statistic=white_noise_result["ljung_box_statistic"],
            ljung_box_p_value=white_noise_result["ljung_box_p_value"],
            is_white_noise=white_noise_result["is_white_noise"],
            # 模型信息
            model_aic=model_result["aic"],
            model_bic=model_result["bic"],
            model_log_likelihood=model_result["log_likelihood"],
            convergence_status=model_result["convergence"],
            # 评估指标
            mape=metrics["mape"],
            mae=metrics["mae"],
            mse=metrics["mse"],
            rmse=metrics["rmse"],
            r_squared=metrics["r_squared"],
            # 残差分析
            residual_mean=residual_result["residual_mean"],
            residual_std=residual_result["residual_std"],
            durbin_watson_stat=residual_result["durbin_watson_stat"],
            residual_normality_p=residual_result["residual_normality_p"],
            # 预测数据
            actual_values=actual.tolist(),
            predicted_values=predicted.tolist(),
            prediction_intervals=model_result["confidence_intervals"],
            # 模型参数
            ar_params=model_result["ar_params"],
            ma_params=model_result["ma_params"],
            # 诊断信息
            warnings=warnings_list,
            execution_time=time.time() - start_time,
        )

        logger.info("ARIMA分析完成，执行时间: %.2f秒", result.execution_time)
        return result, image_bytes

    except Exception as e:
        logger.exception("ARIMA分析失败")
        raise RuntimeError(f"ARIMA分析失败: {e}") from e
