import base64
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from langchain_core.tools import BaseTool, tool

from app.log import logger

from .columns import (
    CreateAggregatedFeatureResult,
    CreateColumnResult,
    CreateInteractionTermResult,
    OperationFailed,
    corr_analys,
    create_aggregated_feature,
    create_column,
    create_interaction_term,
    detect_outliers,
    lag_analys,
)
from .scikit import EvaluateModelResult, SaveModelResult, TrainModelResult, evaluate_model, save_model, train_model
from .scikit_features import (
    FeatureImportanceResult,
    FeatureSelectionResult,
    analyze_feature_importance,
    select_features,
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
    return (
        f"训练结果 (ID='{run_id}'):\n"
        f"模型类型: {result['model_type']}\n"
        f"特征列: {', '.join(result['feature_columns'])}\n"
        f"目标列: {result['target_column']}\n"
    )


def dataframe_tools(df: pd.DataFrame) -> tuple[list[BaseTool], dict[str, TrainModelResult], dict[str, Path]]:
    train_model_cache: dict[str, TrainModelResult] = {}
    save_model_cache: dict[str, Path] = {}

    @tool
    def correlation_analysis_tool(col1: str, col2: str, method: str = "pearson") -> dict[str, Any]:
        """
        执行两个指定列之间的相关性分析。
        支持 Pearson (默认) 和 Spearman 方法。

        Args:
            col1 (str): 第一个要分析的列名。
            col2 (str): 第二个要分析的列名。
            method (str): 相关性计算方法，可以是 'pearson' 或 'spearman'。

        Returns:
            dict: 包含相关系数和p值的结果字典。
        """
        logger.info(f"执行相关性分析: {col1} 与 {col2}，方法: {method}")
        return corr_analys(df, col1, col2, method)

    @tool
    def lag_analysis_tool(time_col1: str, time_col2: str) -> dict[str, Any]:
        """
        计算两个时间字段之间的时滞（单位：秒），并返回分布统计、异常点等信息。

        Args:
            time_col1 (str): 第一个时间列的名称。
            time_col2 (str): 第二个时间列的名称。

        Returns:
            dict: 包含平均时滞、最大时滞、最小时滞、标准差、时滞异常点和时滞分布描述的结果字典。
        """
        logger.info(f"执行时滞分析: {time_col1} 与 {time_col2}")
        return lag_analys(df, time_col1, time_col2)

    @tool
    def detect_outliers_tool(column: str, method: str = "zscore", threshold: int = 3) -> pd.DataFrame:
        """
        在指定列中检测异常值。
        支持 'zscore' (默认) 和 'iqr' 方法。

        Args:
            column (str): 要检测异常值的列名。
            method (str): 异常值检测方法，可以是 'zscore' 或 'iqr'。
            threshold (int): 检测阈值。对于zscore，是标准差倍数；对于iqr，是IQR倍数。

        Returns:
            pd.DataFrame: 包含检测到的异常值的DataFrame。
        """
        logger.info(f"检测异常值: 列 {column}，方法: {method}，阈值: {threshold}")
        return detect_outliers(df, column, method, threshold)

    @tool
    def train_model_tool(
        features: list[str],
        target: str,
        model_type: str = "linear_regression",
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> str:
        """
        训练机器学习模型。
        支持 'linear_regression', 'decision_tree_regressor', 'random_forest_regressor' (回归任务)
        和 'decision_tree_classifier', 'random_forest_classifier' (分类任务)。

        Args:
            features (list[str]): 特征列的名称列表。
            target (str): 目标列的名称。
            model_type (str): 模型类型。
            test_size (float): 测试集占总数据集的比例。
            random_state (int): 随机种子。

        Returns:
            str: 训练结果信息，包含训练结果ID(用于评估模型时引用)和模型类型、特征列、目标列等信息。
        """
        logger.info(f"开始训练模型: {model_type}，特征: {features}，目标: {target}")
        result = train_model(df, features, target, model_type, test_size, random_state)
        run_id = str(uuid.uuid4())
        train_model_cache[run_id] = result
        return _format_train_result_for_llm(run_id, result)

    @tool
    def evaluate_model_tool(trained_model_id: str) -> EvaluateModelResult:
        """
        评估训练好的机器学习模型。
        接受 train_model_tool 函数的返回值作为输入。

        Args:
            trained_model_id (str): 训练结果ID，由 `train_model_tool` 函数返回。

        Returns:
            dict: 包含模型评估指标、消息和预测结果摘要的字典。
        """
        if trained_model_id not in train_model_cache:
            raise ValueError(f"未找到训练结果 ID '{trained_model_id}'。请先调用 train_model_tool 进行训练。")

        logger.info(f"评估模型: 训练结果 ID = {trained_model_id}")
        return evaluate_model(train_model_cache[trained_model_id])

    @tool
    def save_model_tool(trained_model_id: str) -> SaveModelResult:
        """
        保存训练好的机器学习模型及其元数据。

        Args:
            trained_model_id (dict): 训练结果ID，由 `train_model_tool` 函数返回。

        Returns:
            dict: 包含保存结果消息和文件路径的字典。
        """
        if trained_model_id not in train_model_cache:
            raise ValueError(f"未找到训练结果 ID '{trained_model_id}'。请先调用 train_model_tool 进行训练。")

        logger.info(f"保存模型: 训练结果 ID = {trained_model_id}")
        file_path = Path.cwd() / "output" / "models" / uuid.uuid4().hex / "model"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        result = save_model(train_model_cache[trained_model_id], file_path)
        save_model_cache[trained_model_id] = file_path
        logger.info(f"模型已保存到: {file_path.with_suffix('.joblib')}")
        return result

    @tool
    def create_column_tool(
        column_name: str,
        expression: str,
        columns_used: list[str] | None = None,
        description: str | None = None,
    ) -> CreateColumnResult | OperationFailed:
        """
        在DataFrame中创建新列或修改现有列。
        允许使用Python表达式对现有列进行操作，创建复合变量。

        Args:
            column_name (str): 新列的名称，如果已存在则会被替换。
            expression (str): Python表达式，用于计算新列的值。
                            可使用df['列名']或直接使用列名(如果不包含特殊字符)，
                            并可使用NumPy函数(如np.log(), np.sqrt())。
                            示例: "df['A'] + df['B']" 或 "np.log(A) * 2 + B / C"。
            columns_used (list[str], optional): 表达式中使用的列名列表。
            description (str, optional): 新列的描述和用途。

        Returns:
            dict: 包含操作结果的字典，包括新列的基本统计信息和样本值。
        """
        return create_column(df, column_name, expression, columns_used, description)

    @tool
    def create_interaction_term_tool(
        column_name: str,
        columns_to_interact: list[str],
        interaction_type: str = "multiply",
        scale: bool = False,
    ) -> CreateInteractionTermResult | OperationFailed:
        """
        创建交互项作为新列，用于捕捉特征间的相互作用效应。

        Args:
            column_name (str): 新创建的交互项列名。
            columns_to_interact (list[str]): 需要交互的列名列表(至少2个)。
            interaction_type (str): 交互方式，可选:
                                    "multiply": 相乘 (默认，如A*B)
                                    "add": 相加 (如A+B)
                                    "subtract": 相减 (如A-B)
                                    "divide": 相除 (如A/B)
                                    "log_multiply": 取对数后相乘 (如log(A)*log(B))
            scale (bool): 是否对结果进行标准化缩放(均值0,标准差1)。

        Returns:
            dict: 包含操作结果的字典。
        """
        return create_interaction_term(df, column_name, columns_to_interact, interaction_type, scale)

    @tool
    def create_aggregated_feature_tool(
        column_name: str,
        group_by_column: str,
        target_column: str,
        aggregation: str = "mean",
        description: str | None = None,
    ) -> CreateAggregatedFeatureResult | OperationFailed:
        """
        创建基于分组聚合的新特征。
        例如，可以计算同一组内其他记录的平均值、最大值等。

        Args:
            column_name (str): 新创建的聚合特征列名。
            group_by_column (str): 用于分组的列名。
            target_column (str): 需要聚合的目标列名。
            aggregation (str): 聚合函数，可选：
                               "mean"(平均值), "median"(中位数), "sum"(求和),
                               "min"(最小值), "max"(最大值), "std"(标准差),
                               "count"(计数), "nunique"(不同值的数量)
            description (str, optional): 新列的描述和用途。

        Returns:
            dict: 包含操作结果的字典。
        """
        return create_aggregated_feature(df, column_name, group_by_column, target_column, aggregation, description)

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
        result, figure = select_features(df, features, target, method, task_type, n_features, threshold)
        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}
        return result, artifact

    select_features_tool.response_format = "content_and_artifact"

    @tool
    def analyze_feature_importance_tool(
        features: list[str], target: str, method: str = "rf_importance", task_type: str = "auto"
    ) -> tuple[FeatureImportanceResult, dict]:
        """
        分析特征重要性，帮助理解哪些特征对目标变量影响最大。

        Args:
            features (list[str]): 要分析的特征列表
            target (str): 目标变量列名
            method (str): 特征重要性计算方法，可选:
                          "rf_importance" - 随机森林特征重要性(默认)
                          "permutation" - 排列重要性(适用于任意模型)
                          "shap" - SHAP值(提供更详细的解释)
            task_type (str): 任务类型，"regression"、"classification"或"auto"(默认，自动检测)

        Returns:
            dict: 包含特征重要性分析结果的字典
        """
        logger.info(f"开始分析特征重要性，方法: {method}, 特征数: {len(features)}")
        result, figure = analyze_feature_importance(df, features, target, method, task_type)
        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}
        return result, artifact

    analyze_feature_importance_tool.response_format = "content_and_artifact"

    tools = [
        correlation_analysis_tool,
        lag_analysis_tool,
        detect_outliers_tool,
        train_model_tool,
        evaluate_model_tool,
        save_model_tool,
        create_column_tool,
        create_interaction_term_tool,
        create_aggregated_feature_tool,
        select_features_tool,
        analyze_feature_importance_tool,
    ]

    return tools, train_model_cache, save_model_cache


__all__ = ["dataframe_tools"]
