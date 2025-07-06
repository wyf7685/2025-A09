import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, cast

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression
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
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.log import logger


class TrainModelResult(TypedDict):
    model: Any
    X_test: Any
    Y_test: Any
    model_type: str
    message: str
    feature_columns: list[str]
    target_column: str
    label_encoder: Any | None  # 可选的标签编码器，用于分类任务


def train_model(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    model_type: str = "linear_regression",
    test_size: float = 0.2,
    random_state: int = 42,
) -> TrainModelResult:
    """
    训练机器学习模型。
    支持 'linear_regression', 'decision_tree_regressor', 'random_forest_regressor' (回归任务)。
    自动处理目标变量为非数值的情况（分类任务）。

    Args:
        df (pd.DataFrame): 输入的DataFrame。
        features (list[str]): 特征列的名称列表。
        target (str): 目标列的名称。
        model_type (str): 模型类型，可选值包括 'linear_regression', 'decision_tree_regressor',
        'random_forest_regressor', 'decision_tree_classifier', 'random_forest_classifier'。
        test_size (float): 测试集占总数据集的比例。
        random_state (int): 随机种子，用于复现结果。

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

    model = None
    if model_type == "linear_regression":
        model = LinearRegression()
        logger.info("使用线性回归模型进行训练")
    elif model_type == "decision_tree_regressor":
        model = DecisionTreeRegressor(random_state=random_state)
        logger.info("使用决策树回归模型进行训练")
    elif model_type == "random_forest_regressor":
        model = RandomForestRegressor(random_state=random_state)
        logger.info("使用随机森林回归模型进行训练")
    elif model_type == "decision_tree_classifier":  # 新增分类器
        model = DecisionTreeClassifier(random_state=random_state)
        logger.info("使用决策树分类模型进行训练")
    elif model_type == "random_forest_classifier":  # 新增分类器
        model = RandomForestClassifier(random_state=random_state)
        logger.info("使用随机森林分类模型进行训练")
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")

    model.fit(X_train, Y_train)

    return {
        "model": model,
        "X_test": X_test,
        "Y_test": Y_test,
        "model_type": model_type,
        "message": f"模型训练成功。模型类型: {model_type}",
        "feature_columns": features,
        "target_column": target,
        "label_encoder": le,  # 保存编码器
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


class SaveModelResult(TypedDict):
    message: str
    file_path: NotRequired[str]


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
        meta_data = {
            "model_type": model_info["model_type"],
            "feature_columns": model_info["feature_columns"],
            "target_column": model_info["target_column"],
        }
        # 如果有标签编码器，也保存它的类别信息
        if le := model_info.get("label_encoder"):
            meta_data["label_encoder_classes"] = cast("np.ndarray", le.classes_).tolist()

        metadata_path = file_path.with_suffix(".metadata.json")
        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=4)

        return {"message": "保存模型成功"}  # noqa: TRY300
    except Exception as e:
        return {"message": f"保存模型失败: {e}"}
