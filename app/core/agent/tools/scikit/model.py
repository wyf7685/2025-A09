import dataclasses
import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Protocol, TypedDict, cast

import joblib
import numpy as np
import pandas as pd
from pydantic import TypeAdapter
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
from app.utils import escape_tag, resolve_dot_notation

type TaskType = Literal["regression", "classification"]
type SupportedBaseModelType = Literal[
    "linear_regression",
    "decision_tree_regressor",
    "random_forest_regressor",
    "gradient_boosting_regressor",
    "xgboost_regressor",
    "decision_tree_classifier",
    "random_forest_classifier",
    "gradient_boosting_classifier",
    "xgboost_classifier",
    "logistic_regression",
]
type SupportedCompositeModelType = Literal[
    "voting_classifier",
    "voting_regressor",
    "stacking_classifier",
    "stacking_regressor",
    "blending_classifier",
    "blending_regressor",
]
type SupportedModelType = SupportedBaseModelType | SupportedCompositeModelType

MODEL_CONFIG: dict[TaskType, dict[SupportedBaseModelType, str]] = {
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
BASE_MODEL_TASK_TYPE: dict[SupportedBaseModelType, TaskType] = {
    "linear_regression": "regression",
    "decision_tree_regressor": "regression",
    "random_forest_regressor": "regression",
    "gradient_boosting_regressor": "regression",
    "xgboost_regressor": "regression",
    "decision_tree_classifier": "classification",
    "random_forest_classifier": "classification",
    "gradient_boosting_classifier": "classification",
    "xgboost_classifier": "classification",
    "logistic_regression": "classification",
}
COMPOSITE_MODEL_TASK_TYPE: dict[SupportedCompositeModelType, TaskType] = {
    "voting_classifier": "classification",
    "voting_regressor": "regression",
    "stacking_classifier": "classification",
    "stacking_regressor": "regression",
    "blending_classifier": "classification",
    "blending_regressor": "regression",
}
MODEL_TASK_TYPE: dict[SupportedModelType, TaskType] = BASE_MODEL_TASK_TYPE | COMPOSITE_MODEL_TASK_TYPE


class EstimatorLike(Protocol):
    classes_: list[str]

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "EstimatorLike": ...
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray: ...
    def predict_classes(self, X: pd.DataFrame) -> np.ndarray: ...
    def set_params(self, **params: Any) -> "EstimatorLike": ...


def _get_model_instance(model_type: SupportedBaseModelType, random_state: int = 42) -> EstimatorLike:
    """根据模型类型获取模型实例"""
    # 验证模型类型
    if model_type not in MODEL_TASK_TYPE:
        raise ValueError(f"不支持的模型类型: {model_type}")

    # 确定任务类型
    task_type = MODEL_TASK_TYPE[model_type]
    model_path = MODEL_CONFIG[task_type][model_type]

    # 尝试导入模型
    try:
        ModelClass = resolve_dot_notation(model_path)
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
    logger.opt(colors=True).info(f"创建模型: <e>{escape_tag(model_name)}</e>")

    return model


class ModelInstanceInfo(TypedDict):
    model: EstimatorLike
    model_type: SupportedModelType
    hyperparams: dict[str, Any] | None


def create_model(
    model_type: str,
    random_state: int = 42,
    hyperparams: dict[str, Any] | None = None,
) -> ModelInstanceInfo:
    """
    创建机器学习模型实例，但不进行训练。

    支持以下回归模型:
    - 'linear_regression': 线性回归
    - 'decision_tree_regressor': 决策树回归
    - 'random_forest_regressor': 随机森林回归
    - 'gradient_boosting_regressor': 梯度提升树回归
    - 'xgboost_regressor': XGBoost回归

    支持以下分类模型:
    - 'decision_tree_classifier': 决策树分类
    - 'random_forest_classifier': 随机森林分类
    - 'gradient_boosting_classifier': 梯度提升树分类
    - 'xgboost_classifier': XGBoost分类
    - 'logistic_regression': 逻辑回归分类

    Args:
        model_type (str): 模型类型，详见函数文档。
        random_state (int): 随机种子，用于复现结果。
        hyperparams (dict, optional): 模型超参数，如果提供则应用于模型。

    Returns:
        tuple: (模型实例, 模型类型描述信息)
    """
    if model_type not in BASE_MODEL_TASK_TYPE:
        raise ValueError(f"不支持的模型类型: {model_type}")

    try:
        model = _get_model_instance(model_type, random_state)
    except ImportError as e:
        raise ValueError(f"创建模型失败: {e}") from None

    # 应用超参数（如果提供）
    if hyperparams:
        try:
            model.set_params(**hyperparams)
            logger.opt(colors=True).info(f"已应用超参数: <y>{escape_tag(str(hyperparams))}</y>")
        except Exception as e:
            logger.opt(colors=True).warning(f"应用超参数失败: <r>{escape_tag(str(e))}</r>，将使用默认参数")

    return {
        "model": model,
        "model_type": model_type,
        "hyperparams": hyperparams,
    }


@dataclasses.dataclass(eq=False)
class TrainModelResult:
    model: EstimatorLike
    X_test: Any
    Y_test: Any
    model_type: SupportedModelType
    message: str
    feature_columns: list[str]
    target_column: str
    dataset_id: str = ""
    label_encoder: LabelEncoder | None = dataclasses.field(default=None)
    hyperparams: dict[str, Any] | None = dataclasses.field(default=None)


def fit_model(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    model: EstimatorLike,
    model_type: SupportedModelType,
    test_size: float = 0.2,
    random_state: int = 42,
    hyperparams: dict[str, Any] | None = None,
    dataset_id: str = "",
) -> TrainModelResult:
    """
    使用给定的模型实例和数据进行训练。

    Args:
        df (pd.DataFrame): 输入的DataFrame。
        features (list[str]): 特征列的名称列表。
        target (str): 目标列的名称。
        model (Any): 由create_model创建的模型实例。
        model_type (str): 模型类型。
        test_size (float): 测试集占总数据集的比例。
        random_state (int): 随机种子，用于复现结果。
        hyperparams (dict, optional): 记录模型超参数，仅用于信息记录。
        dataset_id (str, optional): 数据集ID，用于记录模型训练的数据来源。

    Returns:
        TrainModelResult: 包含训练好的模型、测试集数据、模型类型及相关信息的字典。
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
        logger.opt(colors=True).info(
            f"目标变量 '<e>{escape_tag(target)}</e>' 已进行标签编码。原始类别: <c>{escape_tag(str(le.classes_))}</c>"
        )

    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=test_size, random_state=random_state)

    if TYPE_CHECKING:
        assert isinstance(X_train, pd.DataFrame)
        assert isinstance(X_test, pd.DataFrame)
        assert isinstance(Y_train, pd.Series)
        assert isinstance(Y_test, pd.Series)

    # 训练模型
    model.fit(X_train, Y_train)

    return TrainModelResult(
        model=model,
        X_test=X_test,
        Y_test=Y_test,
        model_type=model_type,
        message=f"模型训练成功。模型类型: {model_type}",
        feature_columns=features,
        target_column=target,
        dataset_id=dataset_id,
        label_encoder=le,
        hyperparams=hyperparams,
    )


class EvaluateModelResult(TypedDict):
    metrics: dict[str, float | list[float]]
    message: str
    predictions_summary: dict[str, float]  # 预测结果的描述性统计


def evaluate_model(trained_model_info: TrainModelResult) -> EvaluateModelResult:
    """
    评估训练好的机器学习模型。
    接受 fit_model 函数的返回值作为输入。

    Args:
        trained_model_info (dict): 包含训练好的模型和测试集数据的字典，由 `fit_model` 函数返回。

    Returns:
        dict: 包含模型评估指标、消息和预测结果摘要的字典。
    """
    model = trained_model_info.model
    X_test = trained_model_info.X_test
    y_test = trained_model_info.Y_test
    model_type = trained_model_info.model_type

    y_pred = model.predict(X_test)

    metrics = {}
    message = ""

    # 根据模型类型选择评估指标
    task_type = MODEL_TASK_TYPE.get(model_type)
    if task_type == "regression":  # 回归任务
        metrics["mean_squared_error"] = mean_squared_error(y_test, y_pred)
        metrics["r2_score"] = r2_score(y_test, y_pred)
        message = "模型评估完成 (回归任务)。"
    elif task_type == "classification":  # 分类任务
        if le := trained_model_info.label_encoder:  # 如果目标变量被编码过，需要将预测结果也转换为整数
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
            kwds = {"y_true": y_test_classes, "y_pred": y_pred_classes, "average": "weighted", "zero_division": 0}
            metrics["precision"] = precision_score(**kwds)
            metrics["recall"] = recall_score(**kwds)
            metrics["f1_score"] = f1_score(**kwds)
            metrics["confusion_matrix"] = confusion_matrix(y_test_classes, y_pred_classes).tolist()
            message = "模型评估完成 (分类任务)。"

            y_pred_decoded = le.inverse_transform(y_pred_classes)
            y_test_decoded = le.inverse_transform(y_test_classes)
            message += f"\n预测类别示例 (解码后): {y_pred_decoded[:5].tolist()}"
            message += f"\n真实类别示例 (解码后): {y_test_decoded[:5].tolist()}"
        else:  # 没有编码器，直接评估（假设y_test和y_pred已经是可比较的）
            metrics["accuracy"] = accuracy_score(y_test, y_pred)
            kwds = {"y_true": y_test, "y_pred": y_pred, "average": "weighted", "zero_division": 0}
            metrics["precision"] = precision_score(**kwds)
            metrics["recall"] = recall_score(**kwds)
            metrics["f1_score"] = f1_score(**kwds)
            metrics["confusion_matrix"] = confusion_matrix(y_test, y_pred).tolist()
            message = "模型评估完成 (分类任务)。"
    else:
        message = f"不支持对模型类型 '{model_type}' 进行评估。"

    return {
        "metrics": metrics,
        "message": message,
        "predictions_summary": pd.Series(y_pred).describe().to_dict(),
    }


class ModelMetadata(TypedDict):
    model_type: SupportedModelType
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
        model_info (dict): 包含训练好的模型及其信息的字典，由 `fit_model` 函数返回。
        file_path (str): 模型保存的路径。

    Returns:
        dict: 包含保存结果消息和文件路径的字典。
    """
    model = model_info.model
    try:
        joblib.dump(model, file_path.with_suffix(".joblib"))
        # 保存模型的元数据，例如特征列表、目标列、编码器等
        meta_data: ModelMetadata = {
            "model_type": model_info.model_type,
            "feature_columns": model_info.feature_columns,
            "target_column": model_info.target_column,
            "hyperparams": model_info.hyperparams,
        }
        # 如果有标签编码器，也保存它的类别信息
        if le := model_info.label_encoder:
            meta_data["label_encoder_classes"] = cast("np.ndarray", le.classes_).tolist()

        file_path.with_suffix(".metadata.json").write_bytes(
            json.dumps(meta_data, ensure_ascii=False, indent=2).encode()
        )

        return {"message": "保存模型成功", "metadata": meta_data}
    except Exception as e:
        return {"message": f"保存模型失败: {e}"}


def resume_train_result(df: pd.DataFrame, metadata: ModelMetadata, model: EstimatorLike) -> TrainModelResult:
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

    return TrainModelResult(
        model=model,
        X_test=df[metadata["feature_columns"]],
        Y_test=Y,
        model_type=metadata["model_type"],
        message="从文件加载模型",
        feature_columns=metadata["feature_columns"],
        target_column=metadata["target_column"],
        label_encoder=le,
        hyperparams=metadata.get("hyperparams", None),  # 超参数需要重新应用
    )


def load_model(df: pd.DataFrame, file_path: Path) -> tuple[ModelMetadata, TrainModelResult]:
    """
    从文件加载机器学习模型及其元数据。

    Args:
        file_path (str): 模型文件的路径。

    Returns:
        tuple: 包含加载的模型和元数据的元组。
    """
    try:
        model: EstimatorLike = joblib.load(file_path.with_suffix(".joblib"))
        metadata = load_model_metadata(file_path)
        return metadata, resume_train_result(df, metadata, model)
    except Exception:
        logger.opt(colors=True).exception("<r>加载模型失败</r>")
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
            return TypeAdapter(ModelMetadata).validate_json(f.read())
    except Exception:
        logger.opt(colors=True).exception("<r>加载模型元数据失败</r>")
        raise


class PredictionResult(TypedDict):
    """模型预测的结果"""

    message: str  # 预测操作的结果消息
    prediction_dataset_id: str
    predictions_summary: dict[str, float]  # 预测结果的描述性统计
    model_type: SupportedModelType  # 模型类型
    task_type: Literal["regression", "classification"]  # 任务类型


def predict_with_model(
    model_info: TrainModelResult,
    input_data: pd.DataFrame,
    input_features: list[str] | None = None,
) -> tuple[pd.DataFrame, PredictionResult]:
    """
    使用训练好的模型进行预测，并将预测结果保存到新的DataFrame中。

    Args:
        model_info (TrainModelResult): 包含训练好的模型及其信息的字典，由 `fit_model` 函数返回。
        input_data (pd.DataFrame): 要进行预测的输入数据
        input_features (list[str], optional): 输入数据的特征列名列表。如果不提供，将使用model_info中的特征列。

    Returns:
        tuple[pd.DataFrame, PredictionResult]: 包含预测结果的新DataFrame和预测结果信息字典的元组
    """
    model = model_info.model
    model_type = model_info.model_type
    task_type = MODEL_TASK_TYPE.get(model_type)

    if task_type is None:
        raise ValueError(f"不支持的模型类型: {model_type}")

    # 如果没有指定特征列，则使用模型训练时的特征列
    if input_features is None:
        input_features = model_info.feature_columns

    # 验证所有特征列是否都存在
    missing_features = [f for f in input_features if f not in input_data.columns]
    if missing_features:
        raise ValueError(f"输入数据中缺少以下特征列: {', '.join(missing_features)}")

    # 提取特征数据
    X = cast("pd.DataFrame", input_data[input_features].copy())

    # 进行预测
    logger.opt(colors=True).info(f"使用模型 <e>{escape_tag(model_type)}</e> 进行预测")
    predictions: np.ndarray = model.predict(X)

    # 创建结果DataFrame
    result_df = pd.DataFrame()

    # 添加预测结果列
    result_df["predictions"] = predictions

    # 处理分类模型的解码
    decoded: np.ndarray | None = None
    if task_type == "classification" and (le := model_info.label_encoder):
        try:
            decoded = cast("np.ndarray", le.inverse_transform(predictions.astype(int)))
        except Exception as e:
            logger.opt(colors=True).warning(f"无法解码预测结果: <r>{escape_tag(str(e))}</r>")
        else:
            result_df["predictions_decoded"] = decoded
            logger.opt(colors=True).info(f"分类预测结果已解码，样例: <y>{escape_tag(str(decoded[:5]))}</y>")

    # 生成预测结果摘要
    predictions_summary = pd.Series(predictions).describe().to_dict()

    # 构建结果消息
    if task_type == "regression":
        message = f"回归预测完成。预测样例: {predictions[:5]}"
    elif task_type == "classification":
        if decoded is not None:
            message = f"分类预测完成。预测类别样例: {decoded[:5]}"
        else:
            message = f"分类预测完成。预测样例(编码): {predictions[:5]}"
    else:
        message = f"预测完成。预测样例: {predictions[:5]}"

    return result_df, {
        "message": message,
        "prediction_dataset_id": "{{UNSET}}",
        "predictions_summary": predictions_summary,
        "model_type": model_type,
        "task_type": task_type,
    }
