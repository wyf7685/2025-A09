from typing import Any, TypedDict, cast

import numpy as np
import pandas as pd
from sklearn.feature_selection import (
    RFE,
    RFECV,
    SelectKBest,
    SelectPercentile,
    chi2,
    f_regression,
    mutual_info_classif,
    mutual_info_regression,
)

from app.log import logger

from .feature_importance import _create_feature_importance_plot


class FeatureSelectionResult(TypedDict):
    selected_features: list[str]
    feature_importance: dict[str, float]
    message: str
    n_features_original: int
    n_features_selected: int
    method_used: str
    additional_info: dict[str, Any]
    # figure: bytes | None  # 图表数据


def select_features(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    method: str = "rf_importance",
    task_type: str = "auto",
    n_features: int | None = None,
    threshold: float | None = None,
    cv_folds: int = 5,
) -> tuple[FeatureSelectionResult, bytes | None]:
    """
    使用多种方法进行特征选择。

    Args:
        df (pd.DataFrame): 输入数据框
        features (List[str]): 候选特征列表
        target (str): 目标变量列名
        method (str): 特征选择方法，可选:
                      "rf_importance" - 随机森林特征重要性
                      "lasso" - Lasso正则化
                      "rfe" - 递归特征消除
                      "rfecv" - 带交叉验证的递归特征消除
                      "mutual_info" - 互信息
                      "f_regression" - F统计量(回归)
                      "chi2" - 卡方检验(分类，仅适用于非负特征)
        task_type (str): 任务类型，"regression"或"classification"，"auto"将自动检测
        n_features (int, optional): 要选择的特征数量，method为rfe时必须提供
        threshold (float, optional): 特征重要性阈值，只保留重要性大于阈值的特征
        cv_folds (int): 交叉验证折数，用于rfecv方法

    Returns:
        FeatureSelectionResult: 包含选择结果的字典
    """
    # 验证输入参数
    if not all(f in df.columns for f in features):
        missing = set(features) - set(df.columns)
        raise ValueError(f"特征列表中包含不存在的列: {', '.join(missing)}")

    if target not in df.columns:
        raise ValueError(f"目标列 '{target}' 不存在于数据中")

    X = cast("pd.DataFrame", df[features].copy())
    y = cast("pd.Series", df[target].copy())

    # 自动检测任务类型
    if task_type == "auto":
        if y.dtype == "object" or y.dtype == "category" or len(y.unique()) < 10:
            task_type = "classification"
            logger.info(f"自动检测到分类任务，目标列: {target}")
        else:
            task_type = "regression"
            logger.info(f"自动检测到回归任务，目标列: {target}")

    # 检查数据问题
    if cast("pd.Series", X.isna().any()).any():
        logger.warning("数据中包含缺失值，这可能影响特征选择结果")

    # 初始化结果
    result: FeatureSelectionResult = {
        "selected_features": [],
        "feature_importance": {},
        "message": "",
        "n_features_original": len(features),
        "n_features_selected": 0,
        "method_used": method,
        "additional_info": {},
    }

    # 使用不同的方法进行特征选择
    try:
        match method:
            case "rf_importance":
                result = _select_by_random_forest(X, y, features, task_type, threshold, result)
            case "lasso":
                result = _select_by_lasso(X, y, features, task_type, threshold, result)
            case "rfe":
                if n_features is None:
                    raise ValueError("使用RFE方法时必须提供n_features参数")
                result = _select_by_rfe(X, y, features, task_type, n_features, result)
            case "rfecv":
                result = _select_by_rfecv(X, y, features, task_type, cv_folds, result)
            case "mutual_info":
                result = _select_by_mutual_info(X, y, features, task_type, n_features, threshold, result)
            case "f_regression" if task_type == "regression":
                result = _select_by_f_regression(X, y, features, n_features, threshold, result)
            case "chi2" if task_type == "classification":
                # 检查是否有负值，chi2要求非负值
                if (X < 0).any().any():
                    raise ValueError("Chi2方法要求所有特征值非负，请预处理数据后再使用此方法")
                result = _select_by_chi2(X, y, features, n_features, threshold, result)
            case _:
                raise ValueError(f"不支持的方法 '{method}' 或方法与任务类型 '{task_type}' 不匹配")

    except Exception as e:
        logger.error(f"特征选择过程中发生错误: {e}")
        result["message"] = f"特征选择失败: {e}"
        return result, None

    # 更新结果统计
    result["n_features_selected"] = len(result["selected_features"])

    # 如果没有特征被选择，添加警告
    if result["n_features_selected"] == 0:
        result["message"] += "\n警告: 没有特征被选择。请尝试调整阈值或使用不同的方法。"

    # 创建特征重要性图表
    figure = None
    if result["feature_importance"]:
        figure = _create_feature_importance_plot(result["feature_importance"])

    logger.info(
        f"特征选择完成。"
        f"方法: {method}, 从 {result['n_features_original']} 个特征中"
        f"选择了 {result['n_features_selected']} 个"
    )
    return result, figure


def _select_by_random_forest(
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    task_type: str,
    threshold: float | None,
    result: FeatureSelectionResult,
) -> FeatureSelectionResult:
    """使用随机森林特征重要性进行特征选择"""
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

    if task_type == "regression":
        model = RandomForestRegressor(n_estimators=100, random_state=42)
    else:
        model = RandomForestClassifier(n_estimators=100, random_state=42)

    model.fit(X, y)
    importances = model.feature_importances_

    # 创建特征重要性字典
    feature_importance = {features[i]: importances[i] for i in range(len(features))}

    # 根据阈值或排序选择特征
    if threshold is not None:
        mean_importance = None
        selected_features = [f for f, imp in feature_importance.items() if imp >= threshold]
    else:
        # 如果没有阈值，默认选择重要性大于平均值的特征
        mean_importance = np.mean(importances)
        selected_features = [f for f, imp in feature_importance.items() if imp >= mean_importance]

    # 按重要性降序排列
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["selected_features"] = selected_features
    result["message"] = f"使用随机森林特征重要性选择了 {len(selected_features)} 个特征"
    if threshold is not None:
        result["message"] += f" (重要性阈值: {threshold})"
    else:
        result["message"] += f" (重要性阈值: 平均值 {mean_importance:.4f})"

    # 添加特征重要性百分比到额外信息
    total_importance = sum(feature_importance.values())
    importance_percent = {f: imp / total_importance * 100 for f, imp in feature_importance.items()}
    result["additional_info"]["importance_percent"] = importance_percent

    return result


def _select_by_lasso(
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    task_type: str,
    threshold: float | None,
    result: FeatureSelectionResult,
) -> FeatureSelectionResult:
    """使用Lasso正则化进行特征选择"""
    from sklearn.linear_model import Lasso, LogisticRegression

    if task_type == "regression":
        # 对于回归任务使用Lasso
        model = Lasso(alpha=0.01, random_state=42)
    else:
        # 对于分类任务使用L1正则化的逻辑回归
        model = LogisticRegression(penalty="l1", solver="liblinear", random_state=42)

    model.fit(X, y)

    # 获取特征系数
    if task_type == "regression":
        coefs = model.coef_
    else:
        # 对于多类别分类，取绝对系数的平均值
        if len(model.coef_.shape) > 1 and model.coef_.shape[0] > 1:
            coefs = np.mean(np.abs(model.coef_), axis=0)
        else:
            coefs = model.coef_[0] if model.coef_.ndim > 1 else model.coef_

    # 创建特征重要性字典
    feature_importance = {features[i]: abs(coefs[i]) for i in range(len(features))}

    # 根据阈值或非零系数选择特征
    if threshold is not None:
        selected_features = [f for f, imp in feature_importance.items() if imp >= threshold]
    else:
        # 如果没有阈值，选择非零系数的特征
        selected_features = [f for f, imp in feature_importance.items() if imp > 0]

    # 按系数绝对值降序排列
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["selected_features"] = selected_features
    result["message"] = f"使用Lasso正则化选择了 {len(selected_features)} 个特征"
    if threshold is not None:
        result["message"] += f" (系数阈值: {threshold})"
    else:
        result["message"] += " (选择非零系数特征)"

    # 添加原始系数到额外信息
    result["additional_info"]["original_coefficients"] = {features[i]: coefs[i] for i in range(len(features))}

    return result


def _select_by_rfe(
    X: pd.DataFrame, y: pd.Series, features: list[str], task_type: str, n_features: int, result: FeatureSelectionResult
) -> FeatureSelectionResult:
    """使用递归特征消除进行特征选择"""
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

    if task_type == "regression":
        estimator = RandomForestRegressor(n_estimators=100, random_state=42)
    else:
        estimator = RandomForestClassifier(n_estimators=100, random_state=42)

    rfe = RFE(estimator=estimator, n_features_to_select=n_features)
    rfe.fit(X, y)

    # 获取特征排名和掩码
    ranking = rfe.ranking_
    mask = rfe.support_

    # 创建特征重要性字典 (反转排名使得1是最重要的)
    max_rank = max(ranking)
    feature_importance = {features[i]: (max_rank - ranking[i] + 1) / max_rank for i in range(len(features))}

    # 选择被RFE保留的特征
    selected_features = [features[i] for i in range(len(features)) if mask[i]]

    # 按重要性排序
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["selected_features"] = selected_features
    result["message"] = f"使用递归特征消除(RFE)选择了 {len(selected_features)} 个特征"

    # 添加特征排名到额外信息
    result["additional_info"]["feature_ranking"] = {features[i]: int(ranking[i]) for i in range(len(features))}

    return result


def _select_by_rfecv(
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    task_type: str,
    cv_folds: int,
    result: FeatureSelectionResult,
) -> FeatureSelectionResult:
    """使用带交叉验证的递归特征消除进行特征选择"""
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

    if task_type == "regression":
        estimator = RandomForestRegressor(n_estimators=100, random_state=42)
    else:
        estimator = RandomForestClassifier(n_estimators=100, random_state=42)

    rfecv = RFECV(estimator=estimator, cv=cv_folds, scoring="r2" if task_type == "regression" else "accuracy")
    rfecv.fit(X, y)

    # 获取特征排名和掩码
    ranking = rfecv.ranking_
    mask = rfecv.support_

    # 创建特征重要性字典 (反转排名使得1是最重要的)
    max_rank = max(ranking)
    feature_importance = {features[i]: (max_rank - ranking[i] + 1) / max_rank for i in range(len(features))}

    # 选择被RFECV保留的特征
    selected_features = [features[i] for i in range(len(features)) if mask[i]]

    # 按重要性排序
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["selected_features"] = selected_features
    result["message"] = (
        f"使用带交叉验证的递归特征消除(RFECV)选择了 {len(selected_features)} 个特征，最优特征数量为 {rfecv.n_features_}"
    )

    # 添加特征排名和交叉验证分数到额外信息
    result["additional_info"]["feature_ranking"] = {features[i]: int(ranking[i]) for i in range(len(features))}
    result["additional_info"]["cv_scores"] = rfecv.cv_results_["mean_test_score"].tolist()
    result["additional_info"]["optimal_n_features"] = int(rfecv.n_features_)

    return result


def _select_by_mutual_info(
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    task_type: str,
    n_features: int | None,
    threshold: float | None,
    result: FeatureSelectionResult,
) -> FeatureSelectionResult:
    """使用互信息进行特征选择"""
    score_func = mutual_info_regression if task_type == "regression" else mutual_info_classif

    if n_features is not None:
        selector = SelectKBest(score_func=score_func, k=n_features)
    elif threshold is not None:
        selector = SelectPercentile(score_func=score_func)
    else:
        # 默认选择一半的特征
        selector = SelectKBest(score_func=score_func, k=max(1, len(features) // 2))

    selector.fit(X, y)
    scores = selector.scores_

    # 创建特征重要性字典
    feature_importance = {features[i]: scores[i] for i in range(len(features))}

    # 选择特征
    if n_features is not None or threshold is None:
        mask = selector.get_support()
        selected_features = (
            [features[i] for i in range(len(features)) if mask[i]] if mask is not None else features.copy()
        )
    else:
        # 如果使用自定义阈值
        selected_features = [f for f, score in feature_importance.items() if score >= threshold]

    # 按重要性排序
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["selected_features"] = selected_features
    result["message"] = f"使用互信息选择了 {len(selected_features)} 个特征"
    if n_features is not None:
        result["message"] += f" (选择前 {n_features} 个特征)"
    elif threshold is not None:
        result["message"] += f" (互信息阈值: {threshold})"
    else:
        result["message"] += f" (选择前 {max(1, len(features) // 2)} 个特征)"

    return result


def _select_by_f_regression(
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    n_features: int | None,
    threshold: float | None,
    result: FeatureSelectionResult,
) -> FeatureSelectionResult:
    """使用F统计量进行回归问题的特征选择"""
    if n_features is not None:
        selector = SelectKBest(score_func=f_regression, k=n_features)
    elif threshold is not None:
        selector = SelectPercentile(score_func=f_regression)
    else:
        # 默认选择一半的特征
        selector = SelectKBest(score_func=f_regression, k=max(1, len(features) // 2))

    selector.fit(X, y)
    scores = selector.scores_
    p_values = selector.pvalues_

    # 创建特征重要性字典
    feature_importance = {features[i]: scores[i] for i in range(len(features))}

    # 选择特征
    if n_features is not None or threshold is None:
        mask = selector.get_support()
        selected_features = (
            [features[i] for i in range(len(features)) if mask[i]] if mask is not None else features.copy()
        )
    else:
        # 如果使用自定义阈值
        selected_features = [f for f, score in feature_importance.items() if score >= threshold]

    # 按重要性排序
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["selected_features"] = selected_features
    result["message"] = f"使用F统计量选择了 {len(selected_features)} 个特征"
    if n_features is not None:
        result["message"] += f" (选择前 {n_features} 个特征)"
    elif threshold is not None:
        result["message"] += f" (F值阈值: {threshold})"
    else:
        result["message"] += f" (选择前 {max(1, len(features) // 2)} 个特征)"

    # 添加p值到额外信息
    if p_values is not None:
        result["additional_info"]["p_values"] = {features[i]: p_values[i] for i in range(len(features))}

    return result


def _select_by_chi2(
    X: pd.DataFrame,
    y: pd.Series,
    features: list[str],
    n_features: int | None,
    threshold: float | None,
    result: FeatureSelectionResult,
) -> FeatureSelectionResult:
    """使用卡方检验进行分类问题的特征选择"""
    if n_features is not None:
        selector = SelectKBest(score_func=chi2, k=n_features)
    elif threshold is not None:
        selector = SelectPercentile(score_func=chi2)
    else:
        # 默认选择一半的特征
        selector = SelectKBest(score_func=chi2, k=max(1, len(features) // 2))

    selector.fit(X, y)
    scores = selector.scores_
    p_values = selector.pvalues_

    # 创建特征重要性字典
    feature_importance = {features[i]: scores[i] for i in range(len(features))}

    # 选择特征
    if n_features is not None or threshold is None:
        mask = selector.get_support()
        selected_features = (
            [features[i] for i in range(len(features)) if mask[i]] if mask is not None else features.copy()
        )
    else:
        # 如果使用自定义阈值
        selected_features = [f for f, score in feature_importance.items() if score >= threshold]

    # 按重要性排序
    feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))

    result["feature_importance"] = feature_importance
    result["selected_features"] = selected_features
    result["message"] = f"使用卡方检验选择了 {len(selected_features)} 个特征"
    if n_features is not None:
        result["message"] += f" (选择前 {n_features} 个特征)"
    elif threshold is not None:
        result["message"] += f" (卡方值阈值: {threshold})"
    else:
        result["message"] += f" (选择前 {max(1, len(features) // 2)} 个特征)"

    # 添加p值到额外信息
    if p_values is not None:
        result["additional_info"]["p_values"] = {features[i]: p_values[i] for i in range(len(features))}

    return result
