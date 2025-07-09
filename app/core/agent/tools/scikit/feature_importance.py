import io
from typing import Any, NotRequired, TypedDict, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.font_manager import FontProperties

from app.log import logger
from app.utils import escape_tag


def _create_feature_importance_plot(feature_importance: dict[str, float]) -> bytes:
    """创建特征重要性图表并返回字节数据"""
    plt.figure(figsize=(10, 6))

    # 获取按重要性排序的特征
    features = list(feature_importance.keys())
    importances = list(feature_importance.values())

    # 限制显示的特征数量，避免图表过于拥挤
    max_features = 15
    if len(features) > max_features:
        features = features[:max_features]
        importances = importances[:max_features]
        plt.title("特征重要性 (显示前 15 个)")
    else:
        plt.title("特征重要性")

    # 绘制条形图
    y_pos = np.arange(len(features))
    plt.barh(y_pos, importances, align="center")
    plt.yticks(y_pos, features)
    plt.xlabel("重要性")

    # 确保中文正确显示
    for text in plt.gca().get_xticklabels() + plt.gca().get_yticklabels():
        text.set_fontproperties(FontProperties(family=plt.rcParams["font.family"]))

    for item in [plt.gca().title, plt.gca().xaxis.label, plt.gca().yaxis.label]:
        if item:
            item.set_fontproperties(FontProperties(family=plt.rcParams["font.family"]))

    plt.tight_layout()

    # 将图表保存为字节数据
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
    plt.close()
    buffer.seek(0)

    return buffer.getvalue()


class FeatureImportanceResult(TypedDict):
    feature_importance: dict[str, float]
    message: str
    importance_percent: NotRequired[dict[str, float]]
    additional_info: NotRequired[dict[str, Any]]


def analyze_feature_importance(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    method: str = "rf_importance",
    task_type: str = "auto",
) -> tuple[FeatureImportanceResult, bytes | None]:
    """
    分析特征重要性，但不进行特征选择。

    Args:
        df (pd.DataFrame): 输入数据框
        features (list[str]): 要分析的特征列表
        target (str): 目标变量列名
        method (str): 特征重要性计算方法，可选:
                      "rf_importance" - 随机森林特征重要性
                      "permutation" - 排列重要性
                      "linear_model" - 线性模型系数
                      "xgboost" - XGBoost特征重要性
                      "mutual_info" - 互信息
        task_type (str): 任务类型，"regression"或"classification"，"auto"将自动检测

    Returns:
        FeatureImportanceResult: 包含特征重要性的结果
    """
    # 验证输入参数
    if not all(f in df.columns for f in features):
        missing = set(features) - set(df.columns)
        raise ValueError(f"特征列表中包含不存在的列: {', '.join(missing)}")

    if target not in df.columns:
        raise ValueError(f"目标列 '{target}' 不存在于数据中")

    fns = {
        "rf_importance": _analyze_feature_importance_rf,
        "permutation": _analyze_feature_importance_permutation,
        "linear_model": _analyze_feature_importance_coefficients,
        "xgboost": _analyze_feature_importance_xgboost,
        "mutual_info": _analyze_feature_importance_mutual_info,
    }

    if method not in fns:
        raise ValueError(f"不支持的特征重要性计算方法 '{method}'")

    X = cast("pd.DataFrame", df[features].copy())
    y = cast("pd.Series", df[target].copy())

    # 自动检测任务类型
    if task_type == "auto":
        if y.dtype == "object" or y.dtype == "category" or len(y.unique()) < 10:
            task_type = "classification"
        else:
            task_type = "regression"

    logger.opt(colors=True).info(
        f"<g>开始特征重要性分析</>，方法: <y>{escape_tag(method)}</>，任务类型: <e>{escape_tag(task_type)}</>"
    )

    # 初始化结果
    result: FeatureImportanceResult = {"feature_importance": {}, "message": ""}
    figure: bytes | None = None

    try:
        result, figure = fns[method](task_type, X, y, features, result)
    except Exception as e:
        logger.opt(colors=True).exception("<r>特征重要性分析失败</>")
        result["message"] = f"特征重要性分析失败: {e}"

    return result, figure


def _analyze_feature_importance_rf(
    task_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    result: FeatureImportanceResult,
) -> tuple[FeatureImportanceResult, bytes]:
    """使用随机森林模型计算特征重要性"""
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

    # 选择基础模型
    if task_type == "regression":
        model = RandomForestRegressor(n_estimators=100, random_state=42)
    else:
        model = RandomForestClassifier(n_estimators=100, random_state=42)

    # 训练模型
    model.fit(X, y)

    # 获取特征重要性
    importances = model.feature_importances_

    # 创建特征重要性字典
    feature_importance = {features[i]: importances[i] for i in range(len(features))}

    # 按重要性降序排列
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["message"] = f"使用随机森林特征重要性计算了 {len(features)} 个特征的重要性"

    # 添加特征重要性百分比
    total_importance = sum(feature_importance.values())
    importance_percent = {f: imp / total_importance * 100 for f, imp in feature_importance.items()}
    result["importance_percent"] = importance_percent

    # 添加标准差到额外信息（如果可用）
    if hasattr(model, "estimators_"):
        # 计算每棵树的特征重要性
        all_importances = np.array([tree.feature_importances_ for tree in model.estimators_])
        std_importances = np.std(all_importances, axis=0)
        std_importance = {features[i]: std_importances[i] for i in range(len(features))}
        if "additional_info" not in result:
            result["additional_info"] = {}
        result["additional_info"]["std_importance"] = std_importance

    # 创建图表
    figure = _create_feature_importance_plot(feature_importance)

    return result, figure


def _analyze_feature_importance_permutation(
    task_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    result: FeatureImportanceResult,
) -> tuple[FeatureImportanceResult, bytes]:
    """使用排列重要性方法计算特征重要性"""
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.inspection import permutation_importance

    # 选择基础模型
    if task_type == "regression":
        model = RandomForestRegressor(n_estimators=100, random_state=42)
    else:
        model = RandomForestClassifier(n_estimators=100, random_state=42)

    # 训练模型
    model.fit(X, y)

    # 计算排列重要性
    perm_importance = permutation_importance(
        model, X, y, n_repeats=10, random_state=42, scoring="r2" if task_type == "regression" else "accuracy"
    )

    # 创建特征重要性字典
    feature_importance = {features[i]: perm_importance["importances_mean"][i] for i in range(len(features))}

    # 按重要性降序排列
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["message"] = f"使用排列重要性方法计算了 {len(features)} 个特征的重要性"

    # 添加特征重要性百分比
    total_importance = sum(feature_importance.values())
    if total_importance > 0:  # 避免除以零
        importance_percent = {f: imp / total_importance * 100 for f, imp in feature_importance.items()}
        result["importance_percent"] = importance_percent

    # 添加标准差到额外信息
    std_importance = {features[i]: perm_importance["importances_std"][i] for i in range(len(features))}
    if "additional_info" not in result:
        result["additional_info"] = {}
    result["additional_info"]["std_importance"] = std_importance

    # 创建图表
    figure = _create_feature_importance_plot(feature_importance)

    return result, figure


def _analyze_feature_importance_coefficients(
    task_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    result: FeatureImportanceResult,
) -> tuple[FeatureImportanceResult, bytes]:
    """使用线性模型系数的绝对值作为特征重要性"""
    from sklearn.preprocessing import StandardScaler

    # 标准化特征以便公平比较系数
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    if task_type == "regression":
        # 对于回归使用Ridge
        from sklearn.linear_model import Ridge

        model = Ridge(alpha=1.0)
    else:
        # 对于分类使用LogisticRegression
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(penalty="l2", C=1.0, solver="liblinear")

    model.fit(X_scaled, y)

    # 获取系数
    if task_type == "classification" and model.coef_.ndim > 1 and model.coef_.shape[0] > 1:
        # 多类分类情况取平均绝对系数
        coeffs = np.mean(np.abs(model.coef_), axis=0)
    else:
        coeffs = np.abs(model.coef_[0] if model.coef_.ndim > 1 else model.coef_)

    # 创建特征重要性字典
    feature_importance = {features[i]: coeffs[i] for i in range(len(features))}

    # 按重要性降序排列
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["message"] = f"使用线性模型系数计算了 {len(features)} 个特征的重要性"

    # 添加特征重要性百分比
    total_importance = sum(feature_importance.values())
    importance_percent = {f: imp / total_importance * 100 for f, imp in feature_importance.items()}
    result["importance_percent"] = importance_percent

    # 创建图表
    figure = _create_feature_importance_plot(feature_importance)

    return result, figure


def _analyze_feature_importance_xgboost(
    task_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    result: FeatureImportanceResult,
) -> tuple[FeatureImportanceResult, bytes]:
    """使用XGBoost计算特征重要性"""
    import xgboost as xgb

    # 准备数据
    if task_type == "regression":
        model = xgb.XGBRegressor(n_estimators=100, random_state=42)
    else:
        model = xgb.XGBClassifier(n_estimators=100, random_state=42)

    model.fit(X, y)

    # 获取特征重要性
    importances = model.feature_importances_

    # 创建特征重要性字典
    feature_importance = {features[i]: importances[i] for i in range(len(features))}

    # 按重要性降序排列
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["message"] = f"使用XGBoost计算了 {len(features)} 个特征的重要性"

    # 添加特征重要性百分比
    total_importance = sum(feature_importance.values())
    importance_percent = {f: imp / total_importance * 100 for f, imp in feature_importance.items()}
    result["importance_percent"] = importance_percent

    # 创建图表
    figure = _create_feature_importance_plot(feature_importance)

    return result, figure


def _analyze_feature_importance_mutual_info(
    task_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    result: FeatureImportanceResult,
) -> tuple[FeatureImportanceResult, bytes]:
    """使用互信息计算特征重要性"""
    from sklearn.feature_selection import mutual_info_classif, mutual_info_regression

    # 选择合适的互信息函数
    mi_func = mutual_info_regression if task_type == "regression" else mutual_info_classif

    # 计算互信息
    importances = mi_func(X, y, random_state=42)

    # 创建特征重要性字典
    feature_importance = {features[i]: importances[i] for i in range(len(features))}

    # 按重要性降序排列
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["message"] = f"使用互信息计算了 {len(features)} 个特征的重要性"

    # 添加特征重要性百分比
    total_importance = sum(feature_importance.values())
    importance_percent = {f: imp / total_importance * 100 for f, imp in feature_importance.items()}
    result["importance_percent"] = importance_percent

    # 创建图表
    figure = _create_feature_importance_plot(feature_importance)

    return result, figure
