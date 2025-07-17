import ast
import base64
import contextlib
import json
import uuid
from pathlib import Path
from typing import Any, Literal, cast

from langchain_core.tools import BaseTool, tool

from app.const import MODEL_DIR
from app.core.agent.schemas import DatasetID
from app.core.agent.sources import Sources
from app.log import logger
from app.schemas.session import SessionID
from app.services.model_registry import model_registry
from app.utils import escape_tag

from .feature_importance import FeatureImportanceResult, analyze_feature_importance
from .feature_select import FeatureSelectionResult, select_features
from .hyperparam import HyperparamOptResult, LearningCurveResult, optimize_hyperparameters, plot_learning_curve
from .model import (
    EvaluateModelResult,
    ModelInstanceInfo,
    ModelMetadata,
    PredictionResult,
    SaveModelResult,
    TrainModelResult,
    create_model,
    evaluate_model,
    fit_model,
    load_model,
    load_model_metadata,
    predict_with_model,
    save_model,
)
from .model_composite import (
    BlendingOptions,
    CompositeModelOptions,
    StackingOptions,
    VotingOptions,
    create_composite_model,
)


def _format_train_result_for_llm(model_id: str, result: TrainModelResult) -> str:
    """
    格式化训练结果以便于 LLM 理解。
    包括模型类型、特征列、目标列和模型评估指标。

    Args:
        model_id (str): 模型的唯一标识符。
        result (TrainModelResult): 训练结果。

    Returns:
        str: 格式化后的字符串。
    """
    output = (
        f"训练结果 (ID='{model_id}'):\n"
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


def _safe_parse_json_or_dict(data: str) -> dict[str, Any] | None:
    """
    尝试解析字符串或直接返回字典。
    如果是字符串，尝试解析为 JSON 或 Python 字典。
    如果解析失败，返回 None。
    """
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(data)
    with contextlib.suppress(ValueError, SyntaxError):
        return ast.literal_eval(data)
    return None


type ModelID = str


def scikit_tools(
    sources: Sources,
    session_id: SessionID,
) -> tuple[list[BaseTool], dict[ModelID, TrainModelResult], dict[ModelID, Path]]:
    model_instance_cache: dict[ModelID, ModelInstanceInfo] = {}
    train_model_cache: dict[ModelID, TrainModelResult] = {}
    saved_models: dict[ModelID, Path] = {}

    def _cache_model_info(model_info: ModelInstanceInfo) -> ModelID:
        """
        缓存模型信息并生成唯一ID。
        """
        model_id = str(uuid.uuid4())
        model_instance_cache[model_id] = model_info
        return model_id

    @tool
    def create_model_tool(
        model_type: str = "linear_regression",
        hyperparams: dict[str, Any] | str | None = None,
        random_state: int = 42,
    ) -> str:
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
            model_type (str): 模型类型。
            hyperparams (dict|str): 模型超参数，可以是字典或JSON字符串。
            random_state (int): 随机种子。

        Returns:
            str: 模型ID，可用于fit_model_tool进行模型训练。
        """
        # 处理字符串形式的超参数
        parsed_hyperparams = None

        if isinstance(hyperparams, str):
            parsed_hyperparams = _safe_parse_json_or_dict(hyperparams)
            if parsed_hyperparams is None:
                logger.opt(colors=True).warning(
                    f"<y>超参数解析错误</y>: {escape_tag(repr(hyperparams))}，将使用默认参数"
                )
        else:
            parsed_hyperparams = hyperparams

        if parsed_hyperparams:
            parsed_hyperparams = _fix_hyperparams(parsed_hyperparams)
            logger.opt(colors=True).info(f"使用超参数: <y>{escape_tag(str(parsed_hyperparams))}</>")

        try:
            logger.opt(colors=True).info(f"<g>创建模型</>: <e>{escape_tag(model_type)}</>")
            model_info = create_model(model_type, random_state, parsed_hyperparams)
            model_id = _cache_model_info(model_info)

            formatted = f"成功创建模型！\n模型ID: {model_id}\n模型类型: {model_type}"
            if parsed_hyperparams:
                formatted += f"\n应用超参数: {parsed_hyperparams}"
            elif parsed_hyperparams is None and hyperparams is not None:
                formatted += "\n\n超参数解析错误，将使用默认参数"

            return formatted
        except Exception as e:
            logger.opt(colors=True).exception(f"<r>创建模型失败</>: <e>{escape_tag(model_type)}</>")
            return f"创建模型失败: {e}"

    @tool
    def fit_model_tool(
        dataset_id: DatasetID,
        model_id: ModelID,
        features: list[str],
        target: str,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> str:
        """
        使用指定的模型实例和数据进行训练。

        Args:
            dataset_id (str): 操作的数据集ID。
            model_id (str): 由create_model_tool或create_composite_model_tool创建的模型ID
            features (list[str]): 特征列的名称列表。
            target (str): 目标列的名称。
            test_size (float): 测试集占总数据集的比例。
            random_state (int): 随机种子，用于复现结果。

        Returns:
            str: 模型训练结果的格式化信息。模型ID保持不变，可直接用于evaluate_model_tool评估。
        """
        # 检查模型ID是否存在
        if model_id not in model_instance_cache:
            return f"未找到模型ID: {model_id}。请先使用create_model_tool创建模型。"

        model_info = model_instance_cache[model_id]
        model = model_info["model"]
        model_type = model_info["model_type"]
        hyperparams = model_info["hyperparams"]

        try:
            logger.opt(colors=True).info(
                f"<g>训练模型</>: <e>{escape_tag(model_type)}</e>，"
                f"特征: <c>{escape_tag(str(features))}</c>，"
                f"目标: <e>{escape_tag(target)}</e>"
            )
            result = fit_model(
                sources.read(dataset_id), features, target, model, model_type, test_size, random_state, hyperparams
            )

            train_model_cache[model_id] = result
            return _format_train_result_for_llm(model_id, result)
        except Exception as e:
            logger.opt(colors=True).exception(f"<r>训练模型失败</>: <e>{escape_tag(model_type)}</e>")
            return f"训练模型失败: {e}"

    @tool
    def create_composite_model_tool(
        model_ids: list[ModelID],
        composite_type: str = "voting",
        use_features: list[str] | None = None,
        weights: list[float] | None = None,
        voting: Literal["hard", "soft"] | None = None,
        meta_model_type: str | None = None,
        cv_folds: int | None = None,
        validation_split: float | None = None,
        meta_model_hyperparams: dict[str, Any] | None = None,
    ) -> str:
        """
        创建集成模型，组合多个已训练模型以提高性能。

        Args:
            model_ids (list[str]): 已训练模型的ID列表，通过fit_model_tool获得
            composite_type (str): 集成模型类型:
                - "voting": 投票/平均集成(默认)
                - "stacking": 使用交叉验证的堆叠集成
                - "blending": 使用验证集的混合集成
            use_features (list[str], optional): 指定使用的特征子集
            weights (list[float], optional): 各模型的权重，仅用于voting
            voting (str, optional): 投票方式，"hard"或"soft"，仅用于分类的voting
            meta_model_type (str, optional): 元模型类型，仅用于stacking或blending
            cv_folds (int, optional): 交叉验证折数，默认5，仅用于stacking
            validation_split (float, optional): 验证集比例，默认0.2，仅用于blending
            meta_model_hyperparams (dict, optional): 元模型的超参数，仅用于stacking或blending

        Returns:
            str: 集成模型ID，可用于后续的evaluate_model_tool或save_model_tool调用
        """
        # 验证模型ID是否存在
        models = []
        for model_id in model_ids:
            if model_id not in train_model_cache:
                raise ValueError(f"未找到训练好的模型 ID '{model_id}'")
            models.append(train_model_cache[model_id])

        # 根据composite_type创建相应的选项
        options: CompositeModelOptions = {"use_features": use_features} if use_features else {}

        if composite_type == "voting":
            options = cast("VotingOptions", options)
            if weights:
                options["weights"] = weights
            if voting:
                options["voting"] = voting
        elif composite_type == "stacking":
            if not meta_model_type:
                raise ValueError("Stacking集成模型需要指定meta_model_type参数")
            options = cast("StackingOptions", options)
            options["meta_model_type"] = meta_model_type
            if cv_folds:
                options["cv_folds"] = cv_folds
            if meta_model_hyperparams:
                options["meta_model_hyperparams"] = meta_model_hyperparams
        elif composite_type == "blending":
            if not meta_model_type:
                raise ValueError("Blending集成模型需要指定meta_model_type参数")
            options = cast("BlendingOptions", options)
            options["meta_model_type"] = meta_model_type
            if validation_split:
                options["validation_split"] = validation_split
            if meta_model_hyperparams:
                options["meta_model_hyperparams"] = meta_model_hyperparams
        else:
            raise ValueError(f"不支持的复合模型类型: {composite_type}")

        # 创建复合模型
        logger.opt(colors=True).info(
            f"<g>创建复合模型</>: 类型=<e>{escape_tag(composite_type)}</e>, 基础模型数量=<c>{len(model_ids)}</c>"
        )
        model_info = create_composite_model(models, composite_type, options)

        # 生成唯一ID并缓存结果
        model_id = str(uuid.uuid4())
        model_instance_cache[model_id] = model_info

        base_models = [f"{i + 1}. {mid}" for i, mid in enumerate(model_ids)]
        return (
            f"复合模型创建成功 (ID={model_id})\n"
            f"模型类型: {model_info['model_type']}\n"
            f"基础模型: {', '.join(base_models)}\n"
            f"超参数: \n{json.dumps(model_info['hyperparams'], indent=2) if model_info['hyperparams'] else '无'}\n"
        )

    @tool
    def evaluate_model_tool(trained_model_id: ModelID) -> EvaluateModelResult:
        """
        评估训练好的机器学习模型。
        可以评估两种来源的模型：
        1. 通过 fit_model_tool 训练完成的模型
        2. 通过 load_model_tool 加载的之前保存的模型

        Args:
            trained_model_id (str): 模型ID，由 `fit_model_tool` 返回或由 `load_model_tool` 加载。

        Returns:
            dict: 包含模型评估指标、消息和预测结果摘要的字典。
        """
        if trained_model_id not in train_model_cache:
            raise ValueError(f"未找到训练结果 ID '{trained_model_id}'。请先调用 fit_model_tool 进行训练。")

        logger.opt(colors=True).info(f"<g>评估模型</>, ID = <c>{escape_tag(trained_model_id)}</>")
        return evaluate_model(train_model_cache[trained_model_id])

    @tool
    def save_model_tool(model_id: ModelID) -> SaveModelResult:
        """
        保存训练好的机器学习模型及其元数据。

        Args:
            model_id (str): 模型ID，由 `fit_model_tool` 返回。

        Returns:
            dict: 包含保存结果消息和模型元信息的字典。
        """
        if model_id not in train_model_cache:
            raise ValueError(f"未找到训练结果 ID '{model_id}'。请先调用 fit_model_tool 进行训练。")

        logger.opt(colors=True).info(f"<g>保存模型</>: 训练结果 ID = <c>{escape_tag(model_id)}</>")

        # 保存模型文件
        file_path = MODEL_DIR / model_id / "model"
        with contextlib.suppress(Exception):
            file_path = file_path.relative_to(Path.cwd())
        file_path.parent.mkdir(parents=True, exist_ok=True)
        result = save_model(train_model_cache[model_id], file_path)
        saved_models[model_id] = file_path

        # 注册模型到模型管理系统
        if session_id:
            train_result = train_model_cache[model_id]
            # 计算模型性能指标
            evaluation = evaluate_model(train_result)
            metrics = evaluation.get("metrics", {})

            # 生成模型名称
            model_name = f"{train_result['model_type']}_{model_id[:8]}"

            # 注册模型
            registry_id = model_registry.register_model(
                name=model_name,
                model_type=train_result["model_type"],
                session_id=session_id,
                dataset_id="TODO",
                description=f"模型ID: {model_id}",
                features=train_result["feature_columns"],
                target_column=train_result["target_column"],
                metrics=metrics,
                model_path=file_path.with_suffix(".joblib"),
                metadata_path=file_path.with_suffix(".metadata.json"),
            )

            logger.opt(colors=True).info(f"<g>模型已注册到管理系统</>: <c>{registry_id}</>")

        logger.opt(colors=True).info(f"<g>模型已保存到</>: <c>{escape_tag(str(file_path.with_suffix('.joblib')))}</>")
        return result

    @tool
    def load_model_tool(dataset_id: DatasetID, model_id: ModelID) -> ModelMetadata:
        """
        从文件加载训练好的机器学习模型，恢复模型的使用能力。

        该工具适用于以下场景：
        1. 会话中断后恢复：当 agent 会话中断并重新启动时，通过此工具恢复之前保存的模型状态
        2. 跨会话模型使用：在新的分析会话中使用之前训练和保存的模型

        使用此工具时，模型将被加载到内存中，可以立即用于以下操作：
        - 使用 evaluate_model_tool 直接传入该 model_id 进行模型评估
        - 使用 save_model_tool 重新保存模型

        注意：加载模型后无需重新训练，可以直接使用模型ID进行其他操作。

        Args:
            dataset_id (str): 关联的数据集ID。
            model_id (str): 模型ID，由之前会话中的 `fit_model_tool` 返回并通过 `save_model_tool` 保存。

        Returns:
            dict: 包含加载的模型元信息，包括模型类型、特征列、目标列和超参数等。
        """
        if model_id not in saved_models:
            raise ValueError(f"未找到保存的模型 ID '{model_id}'")

        file_path = saved_models[model_id]
        logger.opt(colors=True).info(f"<g>加载模型</>: <c>{escape_tag(str(file_path))}</>")
        metadata, train_result = load_model(sources.read(dataset_id), file_path)
        train_model_cache[model_id] = train_result
        return metadata

    @tool
    def list_saved_models_tool() -> dict[ModelID, ModelMetadata]:
        """
        列出所有已保存的模型元信息。

        Returns:
            list[ModelMetadata]: 包含所有已保存模型的元信息字典的列表。
        """
        logger.opt(colors=True).info("<g>列出所有已保存的模型</>")
        return {model_id: load_model_metadata(file_path) for model_id, file_path in saved_models.items()}

    @tool
    def predict_with_model_tool(
        dataset_id: DatasetID,
        model_id: ModelID,
        input_features: list[str] | None = None,
    ) -> PredictionResult:
        """
        使用训练好的模型进行预测，并将预测结果保存到新的DataFrame中。
        新DataFrame将包含以下列:
            - `predictions`: 模型预测结果
            - `predictions_decoded`: 如果是分类任务，包含解码后的预测结果

        Args:
            dataset_id (str): 要进行预测的输入数据集ID。
            model_id (str): 模型ID，由 `fit_model_tool` 返回。
            input_features (list[str], optional): 输入数据的特征列名列表。如果不提供，将使用训练时使用的特征列。

        Returns:
            dict: 包含预测结果的字典
        """
        if model_id not in train_model_cache:
            raise ValueError(f"未找到训练结果 ID '{model_id}'。请先调用 fit_model_tool 进行训练。")

        logger.opt(colors=True).info(f"<g>使用模型进行预测</>, ID = <c>{escape_tag(model_id)}</>")
        prediction, result = predict_with_model(train_model_cache[model_id], sources.read(dataset_id), input_features)
        result["prediction_dataset_id"] = sources.create(prediction)
        return result

    @tool(response_format="content_and_artifact")
    def select_features_tool(
        dataset_id: DatasetID,
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
            dataset_id (str): 操作的数据集ID。
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
        logger.opt(colors=True).info(
            f"<g>开始特征选择</>，方法: <y>{escape_tag(method)}</>, 候选特征数: <c>{len(features)}</>"
        )
        result, figure = select_features(
            sources.read(dataset_id), features, target, method, task_type, n_features, threshold
        )
        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}
        return result, artifact

    @tool(response_format="content_and_artifact")
    def analyze_feature_importance_tool(
        dataset_id: DatasetID,
        features: list[str],
        target: str,
        method: str = "rf_importance",
        task_type: str = "auto",
    ) -> tuple[FeatureImportanceResult, dict]:
        """
        分析特征重要性，帮助理解哪些特征对目标变量影响最大。

        Args:
            dataset_id (str): 操作的数据集ID。
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
        logger.opt(colors=True).info(
            f"<g>开始分析特征重要性</>，方法: <y>{escape_tag(method)}</>, 特征数: <c>{len(features)}</>"
        )
        result, figure = analyze_feature_importance(sources.read(dataset_id), features, target, method, task_type)
        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}
        return result, artifact

    @tool(response_format="content_and_artifact")
    def optimize_hyperparameters_tool(
        dataset_id: DatasetID,
        features: list[str],
        target: str,
        model_type: str = "random_forest",
        task_type: str = "auto",
        method: str = "grid",
        cv_folds: int = 5,
        scoring: str | None = None,
        param_grid: dict[str, list[Any]] | str | None = None,
        n_iter: int = 20,
    ) -> tuple[HyperparamOptResult, dict]:
        """
        使用网格搜索或随机搜索优化机器学习模型的超参数。

        Args:
            dataset_id (str): 操作的数据集ID。
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
            param_grid: 超参数网格(字典或JSON字符串)，为None时使用预定义的网格
            n_iter: 随机搜索的迭代次数(仅当method="random"时有效)

        Returns:
            优化结果，包含最佳参数、得分等
        """
        logger.opt(colors=True).info(
            f"<g>开始超参数优化</>，模型: <e>{escape_tag(model_type)}</>, 方法: <y>{escape_tag(method)}</>"
        )
        if isinstance(param_grid, str):
            parsed_param_grid = _safe_parse_json_or_dict(param_grid)
            if parsed_param_grid is None:
                raise ValueError(f"无法解析超参数网格: {param_grid}")
            param_grid = parsed_param_grid

        result, figure = optimize_hyperparameters(
            sources.read(dataset_id),
            features,
            target,
            model_type,
            task_type,
            method,
            cv_folds,
            scoring,
            param_grid,
            n_iter,
        )

        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}

        return result, artifact

    @tool(response_format="content_and_artifact")
    def plot_learning_curve_tool(
        dataset_id: DatasetID,
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
            dataset_id (str): 操作的数据集ID。
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
        logger.opt(colors=True).info(f"<g>开始生成学习曲线</>，模型: <e>{escape_tag(model_type)}</>")
        result, figure = plot_learning_curve(
            sources.read(dataset_id), features, target, model_type, task_type, cv_folds, scoring, None, hyperparams
        )

        artifact = {}
        if figure is not None:
            artifact = {"type": "image", "base64_data": base64.b64encode(figure).decode()}

        return result, artifact

    tools = [
        # 特征选择和分析
        select_features_tool,
        analyze_feature_importance_tool,
        # 模型创建和训练
        create_model_tool,
        fit_model_tool,
        # 模型优化
        optimize_hyperparameters_tool,
        plot_learning_curve_tool,
        # 高级模型构建
        create_composite_model_tool,
        # 模型评估和管理
        evaluate_model_tool,
        save_model_tool,
        load_model_tool,
        list_saved_models_tool,
        predict_with_model_tool,
    ]

    return tools, train_model_cache, saved_models


__all__ = ["scikit_tools"]
