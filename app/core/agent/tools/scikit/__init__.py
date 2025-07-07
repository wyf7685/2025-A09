import base64
import contextlib
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pandas as pd
from langchain_core.tools import BaseTool, tool

from app.const import MODEL_DIR
from app.log import logger

from .feature_importance import FeatureImportanceResult, analyze_feature_importance
from .feature_select import FeatureSelectionResult, select_features
from .hyperparam import HyperparamOptResult, LearningCurveResult, optimize_hyperparameters, plot_learning_curve
from .model import (
    EvaluateModelResult,
    ModelMetadata,
    SaveModelResult,
    TrainModelResult,
    evaluate_model,
    load_model,
    load_model_metadata,
    save_model,
    train_model,
)


def _format_train_result_for_llm(run_id: str, result: TrainModelResult) -> str:
    """
    格式化训练结果以便于 LLM 理解。
    包括模型类型、特征列、目标列和模型评估指标。

    Args:
        result (TrainModelResult): 训练结果。

    Returns:
        str: 格式化后的字符串。
    """
    output = (
        f"训练结果 (ID='{run_id}'):\n "
        f"模型类型: {result['model_type']}\n"
        f"特征列: {', '.join(result['feature_columns'])}\n"
        f"目标列: {result['target_column']}"
    )

    # 如果使用了自定义超参数，添加到输出中
    if hyperparams := result.get("hyperparams"):
        output += "\n超参数:"
        for param, value in hyperparams.items():
            output += f"\n  - {param}: {value}"

    return output


def _fix_hyperparams(params: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(params.items()):
        if isinstance(value, float) and value.is_integer():
            # 如果是整数值的浮点数，转换为整数
            params[key] = int(value)
    return params


type TrainModelID = str


def scikit_tools(
    df_ref: Callable[[], pd.DataFrame],
) -> tuple[list[BaseTool], dict[TrainModelID, TrainModelResult], dict[TrainModelID, Path]]:
    train_model_cache: dict[TrainModelID, TrainModelResult] = {}
    saved_models: dict[TrainModelID, Path] = {}

    @tool
    def train_model_tool(
        features: list[str],
        target: str,
        model_type: str = "linear_regression",
        test_size: float = 0.2,
        random_state: int = 42,
        hyperparams: dict[str, Any] | str | None = None,  # 修改参数类型
    ) -> str:
        """
        训练机器学习模型。

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
            features (list[str]): 特征列的名称列表。
            target (str): 目标列的名称。
            model_type (str): 模型类型。
            test_size (float): 测试集占总数据集的比例。
            random_state (int): 随机种子。
            hyperparams (dict | str, optional): 模型超参数，可以是字典或JSON字符串格式。

        Returns:
            str: 训练结果信息，包含训练结果ID(用于评估模型时引用)和模型类型、特征列、目标列等信息。
        """
        logger.info(f"开始训练模型: {model_type}，特征: {features}，目标: {target}")

        # 处理超参数
        hyperparams_parse_error = None
        if hyperparams is not None:
            # 如果是字符串，尝试解析为JSON
            if isinstance(hyperparams, str):
                try:
                    hyperparams = cast("dict[str, Any]", json.loads(hyperparams))
                except json.JSONDecodeError as err:
                    hyperparams_parse_error = (
                        f"注意: 无法解析超参数JSON字符串 {hyperparams}，使用默认超参数\n错误详情: {err}"
                    )
                    logger.warning(f"无法解析超参数JSON字符串: {hyperparams}，使用默认超参数")
                    hyperparams = None

            # 修复超参数类型问题
            if hyperparams:
                hyperparams = _fix_hyperparams(hyperparams)
                logger.info(f"使用自定义超参数: {hyperparams}")

        result = train_model(df_ref(), features, target, model_type, test_size, random_state, hyperparams)
        run_id = str(uuid.uuid4())
        train_model_cache[run_id] = result
        formatted = _format_train_result_for_llm(run_id, result)
        if hyperparams_parse_error:
            formatted += f"\n\n{hyperparams_parse_error}"
        return formatted

    @tool
    def evaluate_model_tool(trained_model_id: TrainModelID) -> EvaluateModelResult:
        """
        评估训练好的机器学习模型。
        可以评估两种来源的模型：
        1. 通过 train_model_tool 训练完成的模型
        2. 通过 load_model_tool 加载的之前保存的模型

        Args:
            trained_model_id (str): 训练结果ID，由 `train_model_tool` 返回或由 `load_model_tool` 加载。

        Returns:
            dict: 包含模型评估指标、消息和预测结果摘要的字典。
        """
        if trained_model_id not in train_model_cache:
            raise ValueError(f"未找到训练结果 ID '{trained_model_id}'。请先调用 train_model_tool 进行训练。")

        logger.info(f"评估模型: 训练结果 ID = {trained_model_id}")
        return evaluate_model(train_model_cache[trained_model_id])

    @tool
    def save_model_tool(trained_model_id: TrainModelID) -> SaveModelResult:
        """
        保存训练好的机器学习模型及其元数据。

        Args:
            trained_model_id (str): 训练结果ID，由 `train_model_tool` 返回。

        Returns:
            dict: 包含保存结果消息和模型元信息的字典。
        """
        if trained_model_id not in train_model_cache:
            raise ValueError(f"未找到训练结果 ID '{trained_model_id}'。请先调用 train_model_tool 进行训练。")

        logger.info(f"保存模型: 训练结果 ID = {trained_model_id}")
        file_path = MODEL_DIR / trained_model_id / "model"
        with contextlib.suppress(Exception):
            file_path = file_path.relative_to(Path.cwd())
        file_path.parent.mkdir(parents=True, exist_ok=True)
        result = save_model(train_model_cache[trained_model_id], file_path)
        saved_models[trained_model_id] = file_path
        logger.info(f"模型已保存到: {file_path.with_suffix('.joblib')}")
        return result

    @tool
    def load_model_tool(trained_model_id: TrainModelID) -> ModelMetadata:
        """
        从文件加载训练好的机器学习模型，恢复模型的使用能力。

        该工具适用于以下场景：
        1. 会话中断后恢复：当 agent 会话中断并重新启动时，通过此工具恢复之前保存的模型状态
        2. 跨会话模型使用：在新的分析会话中使用之前训练和保存的模型

        使用此工具时，模型将被加载到内存中，可以立即用于以下操作：
        - 使用 evaluate_model_tool 直接传入该 trained_model_id 进行模型评估
        - 使用 save_model_tool 重新保存模型

        注意：加载模型后无需重新训练，可以直接使用模型ID进行其他操作。

        Args:
            trained_model_id (str): 训练结果ID，由之前会话中的 `train_model_tool` 返回并通过 `save_model_tool` 保存。

        Returns:
            dict: 包含加载的模型元信息，包括模型类型、特征列、目标列和超参数等。
        """
        if trained_model_id not in saved_models:
            raise ValueError(f"未找到保存的模型 ID '{trained_model_id}'")

        file_path = saved_models[trained_model_id]
        logger.info(f"加载模型: {file_path}")
        metadata, train_result = load_model(df_ref(), file_path)
        train_model_cache[trained_model_id] = train_result
        return metadata

    @tool
    def list_saved_models_tool() -> dict[TrainModelID, ModelMetadata]:
        """
        列出所有已保存的模型元信息。

        Returns:
            list[ModelMetadata]: 包含所有已保存模型的元信息列表。
        """
        logger.info("列出所有已保存的模型")
        return {model_id: load_model_metadata(file_path) for model_id, file_path in saved_models.items()}

    @tool
    def select_features_tool(
        features: list[str],
        target: str,
        method: str = "rf_importance",
        task_type: str = "auto",
        n_features: int | None = None,
        threshold: float | None = None,
    ) -> tuple[FeatureSelectionResult, dict]:
        """
        使用多种方法自动选择最重要的特征子集。

        Args:
            features (list[str]): 候选特征列表
            target (str): 目标变量列名
            method (str): 特征选择方法，可选:
                          "rf_importance" - 随机森林特征重要性(默认)
                          "lasso" - Lasso正则化(适用于线性关系)
                          "rfe" - 递归特征消除(需要指定n_features)
                          "rfecv" - 带交叉验证的递归特征消除(自动确定最佳特征数)
                          "mutual_info" - 互信息(适用于非线性关系)
                          "f_regression" - F统计量(仅回归任务)
                          "chi2" - 卡方检验(仅分类任务，要求特征非负)
            task_type (str): 任务类型，"regression"、"classification"或"auto"(默认，自动检测)
            n_features (int, optional): 要选择的特征数量
            threshold (float, optional): 特征重要性阈值，只保留重要性大于阈值的特征

        Returns:
            dict: 包含选择结果的字典，包括选择的特征列表、特征重要性和相关统计信息
        """
        logger.info(f"开始特征选择，方法: {method}, 候选特征数: {len(features)}")
        result, figure = select_features(df_ref(), features, target, method, task_type, n_features, threshold)
        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}
        return result, artifact

    select_features_tool.response_format = "content_and_artifact"

    @tool
    def analyze_feature_importance_tool(
        features: list[str],
        target: str,
        method: str = "rf_importance",
        task_type: str = "auto",
    ) -> tuple[FeatureImportanceResult, dict]:
        """
        分析特征重要性，帮助理解哪些特征对目标变量影响最大。

        Args:
            features (list[str]): 要分析的特征列表
            target (str): 目标变量列名
            method (str): 特征重要性计算方法，可选:
                            "rf_importance" - 随机森林特征重要性
                            "permutation" - 排列重要性
                            "linear_model" - 线性模型系数
                            "xgboost" - XGBoost特征重要性
                            "mutual_info" - 互信息
            task_type (str): 任务类型，"regression"、"classification"或"auto"(默认，自动检测)

        Returns:
            dict: 包含特征重要性分析结果的字典
        """
        logger.info(f"开始分析特征重要性，方法: {method}, 特征数: {len(features)}")
        result, figure = analyze_feature_importance(df_ref(), features, target, method, task_type)
        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}
        return result, artifact

    analyze_feature_importance_tool.response_format = "content_and_artifact"

    @tool
    def optimize_hyperparameters_tool(
        features: list[str],
        target: str,
        model_type: str = "random_forest",
        task_type: str = "auto",
        method: str = "grid",
        cv_folds: int = 5,
        scoring: str | None = None,
        param_grid: dict[str, list[Any]] | None = None,
        n_iter: int = 20,
    ) -> tuple[HyperparamOptResult, dict]:
        """
        使用网格搜索或随机搜索优化机器学习模型的超参数。

        Args:
            features: 特征列名列表
            target: 目标变量列名
            model_type: 模型类型，可选:
                    - "random_forest" (默认): 随机森林
                    - "decision_tree": 决策树
                    - "svm": 支持向量机
                    - "logistic_regression": 逻辑回归(仅分类)
                    - "ridge": 岭回归(仅回归)
                    - "lasso": Lasso回归(仅回归)
            task_type: 任务类型，"regression"、"classification"或"auto"(默认，自动检测)
            method: 优化方法，"grid"(网格搜索)或"random"(随机搜索)
            cv_folds: 交叉验证折数
            scoring: 评分指标，如"r2"(回归)、"accuracy"(分类)等
            param_grid: 超参数网格，为None时使用预定义的网格
            n_iter: 随机搜索的迭代次数(仅当method="random"时有效)

        Returns:
            优化结果，包含最佳参数、得分等
        """
        logger.info(f"开始超参数优化，模型: {model_type}, 方法: {method}")
        result, figure = optimize_hyperparameters(
            df_ref(), features, target, model_type, task_type, method, cv_folds, scoring, param_grid, n_iter
        )

        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}

        return result, artifact

    optimize_hyperparameters_tool.response_format = "content_and_artifact"

    @tool
    def plot_learning_curve_tool(
        features: list[str],
        target: str,
        model_type: str = "random_forest",
        task_type: str = "auto",
        cv_folds: int = 5,
        scoring: str | None = None,
        hyperparams: dict | None = None,
    ) -> tuple[LearningCurveResult, dict]:
        """
        生成并绘制学习曲线，评估模型性能随训练样本数量的变化。
        学习曲线可以帮助诊断模型是否存在偏差或方差问题。

        Args:
            features: 特征列名列表
            target: 目标变量列名
            model_type: 模型类型，与optimize_hyperparameters_tool相同
            task_type: 任务类型，"regression"、"classification"或"auto"
            cv_folds: 交叉验证折数
            scoring: 评分指标
            hyperparams: 模型超参数字典，为None时使用默认参数

        Returns:
            学习曲线结果及可视化图表
        """
        logger.info(f"开始生成学习曲线，模型: {model_type}")
        result, figure = plot_learning_curve(
            df_ref(), features, target, model_type, task_type, cv_folds, scoring, None, hyperparams
        )

        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}

        return result, artifact

    plot_learning_curve_tool.response_format = "content_and_artifact"

    tools = [
        train_model_tool,
        evaluate_model_tool,
        save_model_tool,
        load_model_tool,
        list_saved_models_tool,
        select_features_tool,
        analyze_feature_importance_tool,
        optimize_hyperparameters_tool,
        plot_learning_curve_tool,
    ]

    return tools, train_model_cache, saved_models


__all__ = ["scikit_tools"]
