"""
预测算法模块包

该包包含多种时间序列预测算法的完整实现，用于备件需求预测。
主要功能:
- 传统统计方法：SMA, EMA, ARIMA等
- 机器学习方法：Random Forest, XGBoost, BP神经网络
- 间歇需求预测：Croston方法
- 数据预处理和特征工程
- 模型评估和结果可视化
"""

import logging
import warnings

import matplotlib as mpl
import matplotlib.pyplot as plt

# 忽略警告
warnings.filterwarnings("ignore")

# 配置matplotlib
mpl.use("Agg")
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

logger = logging.getLogger(__name__)

# 传统统计预测方法
try:
    from .analysis_results import SMAAnalysisResult
    from .sma import sma_forecast_impl

    logger.info("SMA forecasting module loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import SMA forecasting: {e}")
    sma_forecast_impl = None

try:
    from .analysis_results import EMAAnalysisResult
    from .ema import ema_forecast_impl

    logger.info("Exponential smoothing module loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import exponential smoothing: {e}")
    ema_forecast_impl = None

try:
    from .analysis_results import ARIMAAnalysisResult
    from .arima import arima_forecast_impl

    logger.info("ARIMA forecasting module loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import ARIMA forecasting: {e}")
    arima_forecast_impl = None

# 间歇需求预测方法
try:
    from .analysis_results import CrostonAnalysisResult
    from .croston import croston_forecast_impl

    logger.info("Croston forecasting module loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import Croston forecasting: {e}")
    croston_forecast_impl = None

# 机器学习预测方法
try:
    from .forest import forest_try

    logger.info("Random Forest forecasting module loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import Random Forest forecasting: {e}")
    forest_try = None

try:
    # from .xgboost import preprocess_data as xgb_preprocess_data
    from .xgboost import sanitized_gwo, xgboost_forecast

    logger.info("XGBoost forecasting module loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import XGBoost forecasting: {e}")
    xgboost_forecast = None
    sanitized_gwo = None

# 神经网络预测方法
try:
    from .zero_and_bp import zero_and_bp_predict

    logger.info("BP neural network forecasting module loaded successfully")
except ImportError as e:
    logger.warning(f"Could not import BP neural network forecasting: {e}")
    zero_and_bp_predict = None

# 定义公共接口
__all__ = [
    "ARIMAAnalysisResult",
    "CrostonAnalysisResult",
    "EMAAnalysisResult",
    "SMAAnalysisResult",
    "arima_forecast_impl",
    "croston_forecast_impl",
    "ema_forecast_impl",
    "forest_try",
    "sanitized_gwo",
    "sma_forecast_impl",
    "xgboost_forecast",
    "zero_and_bp_predict",
]

# 版本信息
__version__ = "1.0.0"
__author__ = "Spare Parts Forecast Team"
__description__ = "Time series forecasting algorithms for spare parts demand prediction"

# 算法类别映射
ALGORITHM_CATEGORIES = {
    "statistical": ["sma_forecast_try", "ema_forecast_try", "arimaforecast_try"],
    "intermittent": ["croston_forecast_try"],
    "machine_learning": ["forest_try", "xgboost_forecast"],
    "neural_network": ["zero_and_bp_predict"],
}


def get_available_algorithms() -> dict[str, list[str]]:
    """
    获取当前可用的预测算法列表

    Returns:
        dict: 按类别分组的可用算法字典
    """
    available = {}
    for category, algorithms in ALGORITHM_CATEGORIES.items():
        available[category] = []
        for algo in algorithms:
            if globals().get(algo) is not None:
                available[category].append(algo)
    return available


def list_algorithms() -> list[str]:
    """
    列出所有可用的预测算法

    Returns:
        list: 可用算法名称列表
    """
    available = get_available_algorithms()
    all_available = []
    for algorithms in available.values():
        all_available.extend(algorithms)
    return all_available


def get_algorithm_info() -> dict[str, str]:
    """
    获取算法详细信息

    Returns:
        dict: 算法信息字典
    """
    info = {
        "sma_forecast_try": "简单移动平均预测",
        "ema_forecast_try": "指数平滑预测",
        "arimaforecast_try": "ARIMA时间序列预测",
        "croston_forecast_try": "Croston间歇需求预测",
        "forest_try": "随机森林预测",
        "xgboost_forecast": "XGBoost梯度提升预测",
        "zero_and_bp_predict": "BP神经网络预测",
    }

    available = list_algorithms()
    return {algo: info[algo] for algo in available if algo in info}
