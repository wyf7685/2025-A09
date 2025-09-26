"""
预测结果数据结构模块

为各种预测算法提供统一的结构化输出格式。
包含基础数据结构和算法特定的扩展类。
"""

from dataclasses import dataclass, field


@dataclass
class BaseAnalysisResult:
    """预测分析结果的基础数据类"""

    # 基本信息
    algorithm_name: str
    target_column: str

    # 数据信息
    total_samples: int
    train_samples: int
    test_samples: int
    train_start_date: str
    train_end_date: str
    test_start_date: str
    test_end_date: str

    # 预测评估指标
    mape: float
    mae: float | None = None
    mse: float | None = None
    rmse: float | None = None
    r_squared: float | None = None

    # 预测数据
    actual_values: list[float] = field(default_factory=list)
    predicted_values: list[float] = field(default_factory=list)

    # 诊断信息
    warnings: list[str] = field(default_factory=list)
    execution_time: float = 0.0


@dataclass
class ARIMAAnalysisResult(BaseAnalysisResult):
    """ARIMA分析结果的数据类"""

    arima_order: tuple[int, int, int] = (2, 1, 1)
    prediction_intervals: list[tuple[float, float]] = field(default_factory=list)

    # 平稳性检验结果
    adf_statistic: float = 0.0
    adf_p_value: float = 0.0
    is_stationary: bool = False
    critical_values: dict[str, float] = field(default_factory=dict)

    # 随机性检验结果
    ljung_box_statistic: float | None = None
    ljung_box_p_value: float | None = None
    is_white_noise: bool = False

    # 模型拟合信息
    model_aic: float = 0.0
    model_bic: float = 0.0
    model_log_likelihood: float = 0.0
    convergence_status: bool = False

    # 残差分析
    residual_mean: float = 0.0
    residual_std: float = 0.0
    durbin_watson_stat: float = 0.0
    residual_normality_p: float = 0.0

    # 模型参数
    ar_params: list[float] = field(default_factory=list)
    ma_params: list[float] = field(default_factory=list)


@dataclass
class SMAAnalysisResult(BaseAnalysisResult):
    """SMA（简单移动平均）分析结果"""

    # 特定参数
    window_size: int = 3
    mape_single: float = 0.0
    mape_weighted: float = 0.0
    best_weights: list[float] = field(default_factory=list)


@dataclass
class EMAAnalysisResult(BaseAnalysisResult):
    """EMA（指数平滑）分析结果"""

    # 一次指数平滑
    alpha: float = 0.0
    mape_one: float = 0.0

    # 二次指数平滑
    beta: float = 0.0
    mape_two: float = 0.0

    # 三次指数平滑
    gamma: float = 0.0
    season_periods: int = 0
    mape_three: float = 0.0

    # 季节性信息
    has_seasonality: bool = False
    seasonal_components: list[float] = field(default_factory=list)


@dataclass
class CrostonAnalysisResult(BaseAnalysisResult):
    """Croston间歇性需求预测分析结果"""

    # Croston原始方法
    alpha_cst: float = 0.0
    mape_cst: float = 0.0

    # SBA变体
    alpha_sba: float = 0.0
    mape_sba: float = 0.0

    # TSB变体
    alpha_tsb: float = 0.0
    beta_tsb: float = 0.0
    mape_tsb: float = 0.0

    # 间歇性指标
    zero_percentage: float = 0.0
    best_method: str = ""


@dataclass
class RandomForestAnalysisResult(BaseAnalysisResult):
    """随机森林预测分析结果"""

    n_estimators: int = 0
    max_depth: int = 0
    feature_importances: dict[str, float] = field(default_factory=dict)


@dataclass
class XGBoostAnalysisResult(BaseAnalysisResult):
    """XGBoost预测分析结果"""

    learning_rate: float = 0.0
    n_estimators: int = 0
    max_depth: int = 0
    feature_importances: dict[str, float] = field(default_factory=dict)
    early_stopping_rounds: int = 0

    # 灰狼优化相关参数
    gwo_iterations: int = 0
    gwo_agents: int = 0
    best_position: list[float] = field(default_factory=list)


@dataclass
class BPNNAnalysisResult(BaseAnalysisResult):
    """BP神经网络预测分析结果"""

    input_size: int = 0
    hidden_size: int = 0
    learning_rate: float = 0.0
    epochs: int = 0
    batch_size: int = 0
    early_stopping_patience: int = 0

    # 训练历史
    loss_history: list[float] = field(default_factory=list)
    val_loss_history: list[float] = field(default_factory=list)
