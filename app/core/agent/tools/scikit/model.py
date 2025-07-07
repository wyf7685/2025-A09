import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, cast

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from app.log import logger
from app.utils import resolve_dot_notation


class TrainModelResult(TypedDict):
    model: Any
    X_test: Any
    Y_test: Any
    model_type: str
    message: str
    feature_columns: list[str]
    target_column: str
    label_encoder: Any | None  # 可选的标签编码器，用于分类任务
    hyperparams: NotRequired[dict[str, Any] | None]  # 存储使用的超参数


_MODEL_CONFIG = {
    "regression": {
        "linear_regression": "sklearn.linear_model:LinearRegression",
        "decision_tree_regressor": "sklearn.tree:DecisionTreeRegressor",
        "random_forest_regressor": "sklearn.ensemble:RandomForestRegressor",
        "gradient_boosting_regressor": "sklearn.ensemble:GradientBoostingRegressor",
        "xgboost_regressor": "xgboost:XGBRegressor",
    },
    "classification": {
        "decision_tree_classifier": "sklearn.tree:DecisionTreeClassifier",
        "random_forest_classifier": "sklearn.ensemble:RandomForestClassifier",
        "gradient_boosting_classifier": "sklearn.ensemble:GradientBoostingClassifier",
        "xgboost_classifier": "xgboost:XGBClassifier",
        "logistic_regression": "sklearn.linear_model:LogisticRegression",
    },
}


def _get_model_instance(model_type: str, random_state: int = 42) -> Any:
    """根据模型类型获取模型实例"""
    # 确定任务类型
    task_type = "classification" if "classifier" in model_type else "regression"

    # 验证模型类型
    if model_type not in _MODEL_CONFIG.get(task_type, {}):
        raise ValueError(f"不支持的模型类型: {model_type}")

    model_path = _MODEL_CONFIG[task_type][model_type]

    # 尝试导入模型
    try:
        ModelClass = resolve_dot_notation(model_path, default_attr="")
    except (ImportError, AttributeError) as e:
        if "xgboost" in model_path:
            raise ImportError(f"未安装XGBoost库，无法使用 xgb 模型: {model_path}") from e
        raise ImportError(f"无法导入模型 {model_path}: {e}") from e

    # 使用inspect检查构造函数的参数
    init_params = inspect.signature(ModelClass.__init__).parameters

    # 创建构造函数参数字典
    init_kwargs = {}
    if "random_state" in init_params:
        init_kwargs["random_state"] = random_state
    if model_type == "logistic_regression" and "max_iter" in init_params:
        init_kwargs["max_iter"] = 1000

    # 创建模型实例
    model = ModelClass(**init_kwargs)
    model_name = {
        "linear_regression": "线性回归模型",
        "decision_tree_regressor": "决策树回归模型",
        "random_forest_regressor": "随机森林回归模型",
        "gradient_boosting_regressor": "梯度提升树回归模型",
        "xgboost_regressor": "XGBoost回归模型",
        "decision_tree_classifier": "决策树分类模型",
        "random_forest_classifier": "随机森林分类模型",
        "gradient_boosting_classifier": "梯度提升树分类模型",
        "xgboost_classifier": "XGBoost分类模型",
        "logistic_regression": "逻辑回归分类模型",
    }.get(model_type, f"{model_type}模型")
    logger.info(f"使用{model_name}进行训练")

    return model


def train_model(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    model_type: str = "linear_regression",
    test_size: float = 0.2,
    random_state: int = 42,
    hyperparams: dict[str, Any] | None = None,  # 新增参数，接收优化后的超参数
) -> TrainModelResult:
    """
    训练机器学习模型。

    支持以下回归模型:
    - 'linear_regression': 线性回归
    - 'decision_tree_regressor': 决策树回归
    - 'random_forest_regressor': 随机森林回归
    - 'gradient_boosting_regressor': 梯度提升树回归
    - 'xgboost_regressor': XGBoost回归 (如果安装了xgboost)

    支持以下分类模型:
    - 'decision_tree_classifier': 决策树分类
    - 'random_forest_classifier': 随机森林分类
    - 'gradient_boosting_classifier': 梯度提升树分类
    - 'xgboost_classifier': XGBoost分类 (如果安装了xgboost)
    - 'logistic_regression': 逻辑回归分类

    自动处理目标变量为非数值的情况（分类任务）。

    Args:
        df (pd.DataFrame): 输入的DataFrame。
        features (list[str]): 特征列的名称列表。
        target (str): 目标列的名称。
        model_type (str): 模型类型，详见函数文档。
        test_size (float): 测试集占总数据集的比例。
        random_state (int): 随机种子，用于复现结果。
        hyperparams (dict, optional): 模型超参数，如果提供则应用于模型。

    Returns:
        dict: 包含训练好的模型、测试集数据、模型类型及相关信息的字典。
    """
    if not all(f in df.columns for f in features):
        raise ValueError(f"部分特征列 {', '.join(set(features) - set(df.columns))} 不存在。")
    if target not in df.columns:
        raise ValueError(f"目标列 {target} 不存在。")

    X = df[features].copy()
    Y = df[target].copy()

    # 处理分类目标
    le = None
    if Y.dtype == "object" or Y.dtype == "category":
        le = LabelEncoder()
        Y = le.fit_transform(Y)
        logger.info(f"目标变量 '{target}' 已进行标签编码。原始类别: {le.classes_}")

    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=test_size, random_state=random_state)

    if TYPE_CHECKING:
        assert isinstance(X_train, pd.DataFrame)
        assert isinstance(X_test, pd.DataFrame)
        assert isinstance(Y_train, pd.Series)
        assert isinstance(Y_test, pd.Series)

    # 通过配置创建模型实例
    try:
        model = _get_model_instance(model_type, random_state)
    except ImportError as e:
        raise ValueError(f"创建模型失败: {e}") from None

    # 应用优化后的超参数（如果提供）
    if hyperparams:
        try:
            model.set_params(**hyperparams)
            logger.info(f"已应用优化的超参数: {hyperparams}")
        except Exception as e:
            logger.warning(f"应用超参数失败: {e}，将使用默认参数")

    model.fit(X_train, Y_train)

    return {
        "model": model,
        "X_test": X_test,
        "Y_test": Y_test,
        "model_type": model_type,
        "message": f"模型训练成功。模型类型: {model_type}" + ("，应用了优化超参数" if hyperparams else ""),
        "feature_columns": features,
        "target_column": target,
        "label_encoder": le,  # 保存编码器
        "hyperparams": hyperparams,  # 保存使用的超参数
    }


class EvaluateModelResult(TypedDict):
    metrics: dict[str, float | list[float]]
    message: str
    predictions_summary: dict[str, float]  # 预测结果的描述性统计


def evaluate_model(trained_model_info: TrainModelResult) -> EvaluateModelResult:
    """
    评估训练好的机器学习模型。
    接受 train_model 函数的返回值作为输入。

    Args:
        trained_model_info (dict): 包含训练好的模型和测试集数据的字典，由 `train_model` 函数返回。

    Returns:
        dict: 包含模型评估指标、消息和预测结果摘要的字典。
    """
    model = trained_model_info["model"]
    X_test = trained_model_info["X_test"]
    y_test = trained_model_info["Y_test"]  # 修正键名
    model_type = trained_model_info["model_type"]

    y_pred = model.predict(X_test)

    metrics = {}
    message = ""

    # 根据模型类型选择评估指标
    if "regressor" in model_type or "regression" in model_type:  # 回归任务
        metrics["mean_squared_error"] = mean_squared_error(y_test, y_pred)
        metrics["r2_score"] = r2_score(y_test, y_pred)
        message = "模型评估完成 (回归任务)。"
    elif "classifier" in model_type:  # 分类任务
        # 如果目标变量被编码过，需要将预测结果也转换为整数
        if le := trained_model_info.get("label_encoder"):
            # 对于分类模型，y_pred通常是类别索引，但如果模型输出是概率，可能需要argmax
            if hasattr(model, "predict_classes"):  # scikit-learn的旧版本API
                y_pred_classes = model.predict_classes(X_test)
            elif hasattr(model, "predict_proba") and len(model.classes_) > 2:  # 多分类
                y_pred_classes = np.argmax(model.predict_proba(X_test), axis=1)
            else:  # 二分类或直接输出类别
                y_pred_classes = y_pred.astype(int)  # 确保是整数类型

            # y_test也可能需要确保是整数类型，如果之前被编码
            y_test_classes = y_test.astype(int)

            metrics["accuracy"] = accuracy_score(y_test_classes, y_pred_classes)
            metrics["precision"] = precision_score(
                y_test_classes,
                y_pred_classes,
                average="weighted",
                zero_division=0,  # type:ignore
            )
            metrics["recall"] = recall_score(
                y_test_classes,
                y_pred_classes,
                average="weighted",
                zero_division=0,  # type:ignore
            )
            metrics["f1_score"] = f1_score(
                y_test_classes,
                y_pred_classes,
                average="weighted",
                zero_division=0,  # type:ignore
            )
            cm = confusion_matrix(y_test_classes, y_pred_classes)
            metrics["confusion_matrix"] = cm.tolist()
            message = "模型评估完成 (分类任务)。"

            y_pred_decoded = le.inverse_transform(y_pred_classes)
            y_test_decoded = le.inverse_transform(y_test_classes)
            message += f"\n预测类别示例 (解码后): {y_pred_decoded[:5].tolist()}"
            message += f"\n真实类别示例 (解码后): {y_test_decoded[:5].tolist()}"
        else:  # 没有编码器，直接评估（假设y_test和y_pred已经是可比较的）
            metrics["accuracy"] = accuracy_score(y_test, y_pred)
            metrics["precision"] = precision_score(
                y_test,
                y_pred,
                average="weighted",
                zero_division=0,  # type:ignore
            )
            metrics["recall"] = recall_score(
                y_test,
                y_pred,
                average="weighted",
                zero_division=0,  # type:ignore
            )
            metrics["f1_score"] = f1_score(
                y_test,
                y_pred,
                average="weighted",
                zero_division=0,  # type:ignore
            )
            cm = confusion_matrix(y_test, y_pred)
            metrics["confusion_matrix"] = cm.tolist()
            message = "模型评估完成 (分类任务)。"
    else:
        message = f"不支持的模型类型 '{model_type}' 进行评估。"

    return {
        "metrics": metrics,
        "message": message,
        "predictions_summary": pd.Series(y_pred).describe().to_dict(),  # 预测结果的描述性统计
    }


class ModelMetadata(TypedDict):
    model_type: str
    feature_columns: list[str]
    target_column: str
    hyperparams: dict[str, Any] | None
    label_encoder_classes: NotRequired[list[str]]  # 标签编码器的类别列表，如果适用


class SaveModelResult(TypedDict):
    message: str
    metadata: NotRequired[ModelMetadata]


def save_model(model_info: TrainModelResult, file_path: Path) -> SaveModelResult:
    """
    保存训练好的机器学习模型及其元数据。

    Args:
        model_info (dict): 包含训练好的模型及其信息的字典，由 `train_model` 函数返回。
        file_path (str): 模型保存的路径。

    Returns:
        dict: 包含保存结果消息和文件路径的字典。
    """
    model = model_info["model"]
    try:
        joblib.dump(model, file_path.with_suffix(".joblib"))
        # 还可以保存模型的元数据，例如特征列表、目标列、编码器等
        meta_data: ModelMetadata = {
            "model_type": model_info["model_type"],
            "feature_columns": model_info["feature_columns"],
            "target_column": model_info["target_column"],
            "hyperparams": model_info.get("hyperparams", None),
        }
        # 如果有标签编码器，也保存它的类别信息
        if le := model_info.get("label_encoder"):
            meta_data["label_encoder_classes"] = cast("np.ndarray", le.classes_).tolist()

        metadata_path = file_path.with_suffix(".metadata.json")
        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=4)

        return {"message": "保存模型成功", "metadata": meta_data}
    except Exception as e:
        return {"message": f"保存模型失败: {e}"}


def resume_train_result(df: pd.DataFrame, metadata: ModelMetadata, model: Any) -> TrainModelResult:
    """
    从元数据恢复训练结果。

    Args:
        df (pd.DataFrame): 用于训练的数据集。
        metadata (ModelMetadata): 模型的元数据。
        model (Any): 加载的模型实例。

    Returns:
        TrainModelResult: 恢复的训练结果。
    """
    Y = df[metadata["target_column"]].copy()
    le = None
    if Y.dtype == "object" or Y.dtype == "category":
        le = LabelEncoder()
        Y = le.fit_transform(Y)

    return {
        "model": model,
        "X_test": df[metadata["feature_columns"]],
        "Y_test": df[metadata["target_column"]],
        "model_type": metadata["model_type"],
        "message": "从文件加载模型",
        "feature_columns": metadata["feature_columns"],
        "target_column": metadata["target_column"],
        "label_encoder": le,
        "hyperparams": metadata.get("hyperparams", None),  # 超参数需要重新应用
    }


def load_model(df: pd.DataFrame, file_path: Path) -> tuple[ModelMetadata, TrainModelResult]:
    """
    从文件加载机器学习模型及其元数据。

    Args:
        file_path (str): 模型文件的路径。

    Returns:
        tuple: 包含加载的模型和元数据的元组。
    """
    try:
        model = joblib.load(file_path.with_suffix(".joblib"))
        metadata = load_model_metadata(file_path)
        return load_model_metadata(file_path), resume_train_result(df, metadata, model)
    except Exception as e:
        logger.error(f"加载模型失败: {e}")
        raise


def load_model_metadata(file_path: Path) -> ModelMetadata:
    """
    从文件加载模型的元数据。

    Args:
        file_path (Path): 模型文件的路径。

    Returns:
        ModelMetadata: 加载的模型元数据。
    """
    metadata_path = file_path.with_suffix(".metadata.json")
    try:
        with metadata_path.open("r", encoding="utf-8") as f:
            return cast("ModelMetadata", json.load(f))
    except Exception:
        logger.exception("加载模型元数据失败")
        raise
