from typing import Any, Literal, Self, TypedDict, cast

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin

from app.log import logger
from app.utils import escape_tag

from .model import BASE_MODEL_TASK_TYPE, EstimatorLike, ModelInstanceInfo, TrainModelResult, create_model


# 通用选项 - 所有集成模型都可能使用的选项
class CommonOptions(TypedDict, total=False):
    """通用选项，适用于所有集成模型"""

    use_features: list[str] | None  # 使用的特征子集


class VotingOptions(CommonOptions, total=False):
    """投票集成模型选项"""

    weights: list[float] | None  # 各模型的权重
    voting: Literal["hard", "soft"]  # 投票方式，仅用于分类


class StackingOptions(CommonOptions, total=False):
    """Stacking集成模型选项"""

    meta_model_type: str  # 元模型类型
    cv_folds: int  # 交叉验证折数
    meta_model_hyperparams: dict[str, Any] | None  # 元模型超参数


class BlendingOptions(CommonOptions, total=False):
    """Blending集成模型选项"""

    meta_model_type: str  # 元模型类型
    validation_split: float  # 验证集比例
    meta_model_hyperparams: dict[str, Any] | None  # 元模型超参数


# 定义联合类型
type CompositeModelOptions = VotingOptions | StackingOptions | BlendingOptions


def create_composite_model(
    models: list[TrainModelResult],
    composite_type: Literal["voting", "stacking", "blending"] = "voting",
    options: CompositeModelOptions | None = None,
) -> ModelInstanceInfo:
    """
    创建复合模型，如投票分类器、堆叠分类器或混合集成模型。

    Args:
        models (list[TrainModelResult]): 已训练模型的结果列表
        composite_type (str): 复合模型类型：
            - "voting": 投票集成(默认)
            - "stacking": 使用交叉验证的堆叠集成
            - "blending": 使用验证集的混合集成
        options (CompositeModelOptions, optional): 复合模型的选项，根据composite_type确定
            对于所有类型:
                - use_features (list[str], optional): 指定使用的特征子集
            对于"voting":
                - weights (list[float], optional): 各模型权重
                - voting (str, optional): 投票方式，"hard"或"soft"，仅用于分类
            对于"stacking":
                - meta_model_type (str): 元模型类型
                - cv_folds (int): 交叉验证折数
                - meta_model_hyperparams (dict): 元模型超参数
            对于"blending":
                - meta_model_type (str): 元模型类型
                - validation_split (float): 验证集比例
                - meta_model_hyperparams (dict): 元模型超参数

    Returns:
        ModelInstanceInfo: 创建的复合模型信息

    Raises:
        ValueError: 当模型类型不兼容或参数错误时
    """
    if not models or len(models) < 2:
        raise ValueError("需要至少两个模型结果来创建复合模型")

    options = options or {}

    # 验证模型兼容性
    _validate_model_compatibility(models)

    # 确定模型类型（分类或回归）
    is_classification = "classifier" in models[0]["model_type"]

    # 根据集成类型创建相应模型
    if composite_type == "voting":
        return _create_voting_model(models, cast("VotingOptions", options), is_classification)
    if composite_type == "stacking":
        return _create_stacking_model(models, cast("StackingOptions", options), is_classification)
    if composite_type == "blending":
        return _create_blending_model(models, cast("BlendingOptions", options), is_classification)

    raise ValueError(f"不支持的复合模型类型: {composite_type}")


def _validate_model_compatibility(models: list[TrainModelResult]) -> None:
    """验证模型兼容性"""
    # 确定模型类型（分类或回归）
    is_classification = "classifier" in models[0]["model_type"]

    # 验证所有模型类型一致
    for model in models[1:]:
        current_is_classification = "classifier" in model["model_type"]
        if current_is_classification != is_classification:
            raise ValueError("所有模型必须是同一类型（分类或回归）")

    # 验证所有模型训练特征输入
    feature_sets = [set(model["feature_columns"]) for model in models]
    if not all(feature_sets[0] == features for features in feature_sets):
        raise ValueError("所有模型的特征列必须一致")

    # 验证所有模型的目标列一致
    target_columns = {model["target_column"] for model in models}
    if len(target_columns) != 1:
        raise ValueError("所有模型的目标列必须一致")


def _create_voting_model(
    models: list[TrainModelResult],
    options: VotingOptions,
    is_classification: bool,
) -> ModelInstanceInfo:
    """创建投票集成模型"""
    # 验证权重列表长度
    weights = options.get("weights")
    if weights and len(weights) != len(models):
        raise ValueError(f"权重列表长度({len(weights)})必须与模型数量({len(models)})相同")

    # 准备构建投票模型
    estimators = [(f"model_{i}", model["model"]) for i, model in enumerate(models)]

    if is_classification:
        voting = options.get("voting", "hard")
        if voting not in ["hard", "soft"]:
            raise ValueError('分类投票方式必须是"hard"或"soft"')
        from sklearn.ensemble import VotingClassifier

        composite_model = VotingClassifier(estimators=estimators, voting=voting, weights=weights)
        logger.opt(colors=True).info(
            f"<g>创建投票分类器</>，投票方式: <y>{escape_tag(str(voting))}</y>，使用<e>{len(estimators)}</e>个基础模型"
        )
        model_type = "voting_classifier"
    else:
        voting = None
        from sklearn.ensemble import VotingRegressor

        composite_model = VotingRegressor(estimators=estimators, weights=weights)
        logger.opt(colors=True).info(f"<g>创建投票回归器</>，使用<e>{len(estimators)}</e>个基础模型")
        model_type = "voting_regressor"

    # 构建超参数字典
    hyperparams = {"weights": weights, "voting": voting if is_classification else None}

    return {
        "model": cast("EstimatorLike", composite_model),
        "model_type": model_type,
        "hyperparams": hyperparams,
    }


def _create_stacking_model(
    models: list[TrainModelResult], options: StackingOptions, is_classification: bool
) -> ModelInstanceInfo:
    """创建堆叠集成模型"""
    # 验证并获取元模型类型
    meta_model_type = options.get("meta_model_type")
    if not meta_model_type:
        raise ValueError("Stacking集成模型需要指定meta_model_type参数")
    if meta_model_type not in BASE_MODEL_TASK_TYPE:
        raise ValueError(f"不支持的元模型类型: {meta_model_type}")

    # 获取交叉验证折数
    cv_folds = options.get("cv_folds", 5)

    # 获取元模型超参数
    meta_model_hyperparams = options.get("meta_model_hyperparams")

    # 创建元模型
    meta_estimator_info = create_model(meta_model_type, hyperparams=meta_model_hyperparams)
    meta_estimator = meta_estimator_info["model"]

    # 准备基础模型
    estimators = [(f"model_{i}", model["model"]) for i, model in enumerate(models)]

    if is_classification:
        from sklearn.ensemble import StackingClassifier

        composite_model = StackingClassifier(
            estimators=estimators, final_estimator=meta_estimator, cv=cv_folds, stack_method="auto"
        )
        logger.opt(colors=True).info(
            f"<g>创建堆叠分类器</>，"
            f"使用<e>{len(estimators)}</e>个基础模型，"
            f"元模型: <y>{escape_tag(meta_model_type)}</y>"
        )
        model_type = "stacking_classifier"
    else:
        from sklearn.ensemble import StackingRegressor

        composite_model = StackingRegressor(estimators=estimators, final_estimator=meta_estimator, cv=cv_folds)
        logger.opt(colors=True).info(
            f"<g>创建堆叠回归器</>，"
            f"使用<e>{len(estimators)}</e>个基础模型，"
            f"元模型: <y>{escape_tag(meta_model_type)}</y>"
        )
        model_type = "stacking_regressor"

    # 构建超参数字典
    hyperparams = {
        "meta_model_type": meta_model_type,
        "cv_folds": cv_folds,
        "meta_model_hyperparams": meta_model_hyperparams,
    }

    return {
        "model": cast("EstimatorLike", composite_model),
        "model_type": model_type,
        "hyperparams": hyperparams,
    }


class BlendingClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, base_estimators: list[Any], meta_estimator: Any, validation_split: float = 0.2) -> None:
        self.base_estimators = base_estimators
        self.meta_estimator = meta_estimator
        self.validation_split = validation_split
        self.classes_ = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> Self:
        # 分割数据集
        from sklearn.model_selection import train_test_split

        X_base, X_meta, y_base, y_meta = train_test_split(X, y, test_size=self.validation_split, random_state=42)

        # 训练基础模型
        for estimator in self.base_estimators:
            estimator.fit(X_base, y_base)

        # 生成元特征
        meta_features = self._generate_meta_features(cast("pd.DataFrame", X_meta))

        # 训练元模型
        self.meta_estimator.fit(meta_features, y_meta)

        # 保存类别信息
        self.classes_ = np.unique(y)

        return self

    def _generate_meta_features(self, X: pd.DataFrame) -> np.ndarray:
        """生成元特征"""
        return np.column_stack(
            [
                model.predict_proba(X)
                if hasattr(model, "predict_proba")
                else np.column_stack([model.predict(X), 1 - model.predict(X)])
                for model in self.base_estimators
            ]
        )

    def predict(self, X: pd.DataFrame) -> Any:
        meta_features = self._generate_meta_features(X)
        return self.meta_estimator.predict(meta_features)

    def predict_proba(self, X: pd.DataFrame) -> Any:
        meta_features = self._generate_meta_features(X)
        return self.meta_estimator.predict_proba(meta_features)


class BlendingRegressor(RegressorMixin, BaseEstimator):
    def __init__(self, base_estimators: list[Any], meta_estimator: Any, validation_split: float = 0.2) -> None:
        self.base_estimators = base_estimators
        self.meta_estimator = meta_estimator
        self.validation_split = validation_split

    def fit(self, X: pd.DataFrame, y: pd.Series) -> Self:
        # 分割数据集
        from sklearn.model_selection import train_test_split

        X_base, X_meta, y_base, y_meta = train_test_split(X, y, test_size=self.validation_split, random_state=42)

        # 训练基础模型
        for estimator in self.base_estimators:
            estimator.fit(X_base, y_base)

        # 生成元特征
        meta_features = np.column_stack([model.predict(X_meta).reshape(-1, 1) for model in self.base_estimators])

        # 训练元模型
        self.meta_estimator.fit(meta_features, y_meta)

        return self

    def predict(self, X: pd.DataFrame) -> Any:
        meta_features = np.column_stack([model.predict(X).reshape(-1, 1) for model in self.base_estimators])
        return self.meta_estimator.predict(meta_features)


def _create_blending_model(
    models: list[TrainModelResult], options: BlendingOptions, is_classification: bool
) -> ModelInstanceInfo:
    """创建混合集成模型"""
    # 验证并获取元模型类型
    meta_model_type = options.get("meta_model_type")
    if not meta_model_type:
        raise ValueError("Blending集成模型需要指定meta_model_type参数")
    if meta_model_type not in BASE_MODEL_TASK_TYPE:
        raise ValueError(f"不支持的元模型类型: {meta_model_type}")

    # 获取验证集比例
    validation_split = options.get("validation_split", 0.2)

    # 获取元模型超参数
    meta_model_hyperparams = options.get("meta_model_hyperparams")

    # 创建元模型
    meta_estimator_info = create_model(meta_model_type, hyperparams=meta_model_hyperparams)
    meta_estimator = meta_estimator_info["model"]

    # 准备基础模型
    base_models = [model["model"] for model in models]

    if is_classification:
        composite_model = BlendingClassifier(base_models, meta_estimator, validation_split)
        logger.opt(colors=True).info(
            f"<g>创建混合分类器</>，"
            f"使用<e>{len(base_models)}</e>个基础模型，"
            f"元模型: <y>{escape_tag(meta_model_type)}</y>"
        )
        model_type = "blending_classifier"
    else:
        composite_model = BlendingRegressor(base_models, meta_estimator, validation_split)
        logger.opt(colors=True).info(
            f"<g>创建混合回归器</>，"
            f"使用<e>{len(base_models)}</e>个基础模型，"
            f"元模型: <y>{escape_tag(meta_model_type)}</y>"
        )
        model_type = "blending_regressor"

    # 构建超参数字典
    hyperparams = {
        "meta_model_type": meta_model_type,
        "validation_split": validation_split,
        "meta_model_hyperparams": meta_model_hyperparams,
    }

    return {
        "model": cast("EstimatorLike", composite_model),
        "model_type": model_type,
        "hyperparams": hyperparams,
    }
