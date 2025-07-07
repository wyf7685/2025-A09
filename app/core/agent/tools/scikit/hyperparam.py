import io
import time
from typing import Any, TypedDict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.font_manager import FontProperties
from scipy.stats import randint, uniform
from sklearn.metrics import make_scorer, mean_squared_error
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, learning_curve

from app.log import logger
from app.utils import resolve_dot_notation


class HyperparamOptResult(TypedDict):
    """超参数优化结果类型"""

    best_params: dict[str, Any]
    best_score: float
    cv_results: dict[str, list[float]]
    model_type: str
    optimization_method: str
    message: str
    score_metric: str
    execution_time: float
    additional_info: dict[str, Any]
    param_importance: dict[str, float]


def optimize_hyperparameters(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    model_type: str = "random_forest",
    task_type: str = "auto",
    method: str = "grid",
    cv_folds: int = 5,
    scoring: str | None = None,
    param_grid: dict[str, list[Any]] | None = None,
    n_iter: int = 20,
    random_state: int = 42,
) -> tuple[HyperparamOptResult, bytes | None]:
    """
    使用网格搜索或随机搜索优化机器学习模型的超参数。

    Args:
        df: 输入数据框
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
        scoring: 评分指标，默认为None(使用模型默认评分)
        param_grid: 超参数网格，为None时使用预定义的网格
        n_iter: 随机搜索的迭代次数(仅当method="random"时有效)
        random_state: 随机数种子

    Returns:
        HyperparamOptResult: 优化结果，包含最佳参数、得分等
        bytes | None: 参数重要性图表数据
    """
    start_time = time.time()

    # 验证输入参数
    if not all(f in df.columns for f in features):
        missing = set(features) - set(df.columns)
        raise ValueError(f"特征列表中包含不存在的列: {', '.join(missing)}")

    if target not in df.columns:
        raise ValueError(f"目标列 '{target}' 不存在于数据中")

    X = df[features].copy()
    y = df[target].copy()

    # 自动检测任务类型
    if task_type == "auto":
        if y.dtype == "object" or y.dtype == "category" or len(y.unique()) < 10:
            task_type = "classification"
            logger.info(f"自动检测到分类任务，目标列: {target}")
        else:
            task_type = "regression"
            logger.info(f"自动检测到回归任务，目标列: {target}")

    # 检查数据问题
    if X.isna().any().any():  # type:ignore
        logger.warning("数据中包含缺失值，这可能影响超参数优化结果")

    # 选择评分指标
    if scoring is None:
        scoring = "r2" if task_type == "regression" else "accuracy"

    # 将scoring转换为sklearn的评分器
    scoring_name = scoring
    if task_type == "regression":
        if scoring == "rmse":
            scoring = make_scorer(  # type:ignore
                lambda y_true, y_pred: -np.sqrt(mean_squared_error(y_true, y_pred)),
            )
        elif scoring == "mse":
            scoring = "neg_mean_squared_error"
        elif scoring == "r2":
            scoring = "r2"
    else:
        if scoring == "f1":
            scoring = "f1"
        elif scoring == "precision":
            scoring = "precision"
        elif scoring == "recall":
            scoring = "recall"
        elif scoring == "accuracy":
            scoring = "accuracy"

    # 选择模型和参数网格
    model, param_grid_dict = _get_model_and_param_grid(model_type, task_type, random_state)

    # 根据方法选择合适的参数网格
    if method == "grid":
        # 网格搜索使用列表形式的参数网格
        param_grid = param_grid_dict["grid"]
        search = GridSearchCV(model, param_grid, cv=cv_folds, scoring=scoring, return_train_score=True, n_jobs=-1)
    elif method == "random":
        # 随机搜索使用分布形式的参数网格
        param_grid = param_grid_dict["random"]
        search = RandomizedSearchCV(
            model,
            param_grid,
            n_iter=n_iter,
            cv=cv_folds,
            scoring=scoring,
            return_train_score=True,
            random_state=random_state,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"不支持的优化方法: {method}")

    # 执行搜索
    logger.info(f"开始{method}搜索优化 {model_type} 模型超参数...")
    search.fit(X, y)

    # 计算参数重要性
    param_importance = _calculate_param_importance(search)

    # 准备结果
    result = HyperparamOptResult(
        best_params=search.best_params_,
        best_score=search.best_score_,
        cv_results={
            "mean_test_score": search.cv_results_["mean_test_score"].tolist(),
            "std_test_score": search.cv_results_["std_test_score"].tolist(),
            "mean_train_score": search.cv_results_["mean_train_score"].tolist(),
            "std_train_score": search.cv_results_["std_train_score"].tolist(),
        },
        model_type=model_type,
        optimization_method=method,
        message=f"使用{method}搜索优化了 {model_type} 模型超参数",
        score_metric=scoring_name,
        execution_time=time.time() - start_time,
        additional_info={
            "cv_folds": cv_folds,
            "task_type": task_type,
            "n_samples": len(X),
            "n_features": len(features),
            "feature_list": features,
        },
        param_importance=param_importance,
    )

    # 创建参数重要性图表
    figure = None
    if param_importance:
        figure = _create_param_importance_plot(param_importance)

    # 获取交叉验证各折的最佳得分
    best_idx = np.argmax(search.cv_results_["mean_test_score"])
    cv_scores = []
    for i in range(cv_folds):
        try:
            cv_scores.append(search.cv_results_[f"split{i}_test_score"][best_idx])
        except KeyError:
            break

    if cv_scores:
        result["additional_info"]["cv_fold_scores"] = cv_scores

    logger.info(
        f"超参数优化完成。方法: {method}, "
        f"最佳得分 ({scoring_name}): {search.best_score_:.4f}, "
        f"最佳参数: {search.best_params_}"
    )
    return result, figure


_MODEL_PARAM_GRID = {
    "regression": {
        "random_forest": {
            "model": "sklearn.ensemble:RandomForestRegressor",
            "grid": {
                "n_estimators": [50, 100, 200],
                "max_depth": [None, 10, 20, 30],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4],
                "max_features": ["sqrt", "log2", None],
            },
        },
        "decision_tree": {
            "model": "sklearn.tree:DecisionTreeRegressor",
            "grid": {
                "max_depth": [None, 5, 10, 15, 20],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4, 8],
                "max_features": ["sqrt", "log2", None],
            },
        },
        "gradient_boosting_regressor": {
            "model": "sklearn.ensemble:GradientBoostingRegressor",
            "grid": {
                "n_estimators": [50, 100, 200],
                "learning_rate": [0.01, 0.05, 0.1, 0.2],
                "max_depth": [3, 5, 7, 9],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4],
                "subsample": [0.8, 0.9, 1.0],
            },
        },
        "xgboost_regressor": {
            "model": "xgboost:XGBRegressor",
            "grid": {
                "n_estimators": [50, 100, 200],
                "learning_rate": [0.01, 0.05, 0.1, 0.2],
                "max_depth": [3, 5, 7, 9],
                "min_child_weight": [1, 3, 5],
                "subsample": [0.8, 0.9, 1.0],
                "colsample_bytree": [0.8, 0.9, 1.0],
                "gamma": [0, 0.1, 0.2],
            },
        },
        "svm": {
            "model": "sklearn.svm:SVR",
            "grid": {
                "kernel": ["linear", "poly", "rbf"],
                "C": [0.1, 1, 10, 100],
                "gamma": ["scale", "auto", 0.1, 1],
            },
        },
        "ridge": {
            "model": "sklearn.linear_model:Ridge",
            "grid": {
                "alpha": [0.1, 1, 10, 100],
                "fit_intercept": [True, False],
                "solver": ["auto", "svd", "cholesky", "lsqr", "sparse_cg", "sag", "saga"],
            },
        },
        "lasso": {
            "model": "sklearn.linear_model:Lasso",
            "grid": {
                "alpha": [0.001, 0.01, 0.1, 1, 10],
                "fit_intercept": [True, False],
                "selection": ["cyclic", "random"],
            },
        },
    },
    "classification": {
        "random_forest": {
            "model": "sklearn.ensemble:RandomForestClassifier",
            "grid": {
                "n_estimators": [50, 100, 200],
                "max_depth": [None, 10, 20, 30],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4],
                "max_features": ["sqrt", "log2", None],
            },
        },
        "decision_tree": {
            "model": "sklearn.tree:DecisionTreeClassifier",
            "grid": {
                "max_depth": [None, 5, 10, 15, 20],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4, 8],
                "max_features": ["sqrt", "log2", None],
            },
        },
        "gradient_boosting_classifier": {
            "model": "sklearn.ensemble:GradientBoostingClassifier",
            "grid": {
                "n_estimators": [50, 100, 200],
                "learning_rate": [0.01, 0.05, 0.1, 0.2],
                "max_depth": [3, 5, 7, 9],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4],
                "subsample": [0.8, 0.9, 1.0],
            },
        },
        "xgboost_classifier": {
            "model": "xgboost:XGBClassifier",
            "grid": {
                "n_estimators": [50, 100, 200],
                "learning_rate": [0.01, 0.05, 0.1, 0.2],
                "max_depth": [3, 5, 7, 9],
                "min_child_weight": [1, 3, 5],
                "subsample": [0.8, 0.9, 1.0],
                "colsample_bytree": [0.8, 0.9, 1.0],
                "gamma": [0, 0.1, 0.2],
            },
        },
        "svm": {
            "model": "sklearn.svm:SVC",
            "grid": {
                "kernel": ["linear", "poly", "rbf"],
                "C": [0.1, 1, 10, 100],
                "gamma": ["scale", "auto", 0.1, 1],
                "probability": [True],  # 始终使用概率估计
            },
        },
        "logistic_regression": {
            "model": "sklearn.linear_model:LogisticRegression",
            "grid": {
                "C": [0.1, 1, 10, 100],
                "penalty": ["l1", "l2", "elasticnet", None],
                "solver": ["lbfgs", "liblinear", "saga"],
                "fit_intercept": [True, False],
                "max_iter": [1000],
            },
        },
    },
}


def _get_model_and_param_grid(model_type: str, task_type: str, random_state: int) -> tuple[Any, dict[str, Any]]:
    """获取指定模型类型和任务类型的模型实例和默认参数网格"""
    import inspect

    # 验证任务类型
    if task_type not in _MODEL_PARAM_GRID:
        raise ValueError(f"不支持的任务类型: {task_type}")

    # 验证模型类型
    if model_type not in _MODEL_PARAM_GRID[task_type]:
        raise ValueError(f"不支持的{task_type}模型类型: {model_type}")

    model_config = _MODEL_PARAM_GRID[task_type][model_type]

    # 尝试导入模型
    try:
        # 使用resolve_dot_notation函数导入模型类
        ModelClass = resolve_dot_notation(model_config["model"], default_attr="")
    except (ImportError, AttributeError) as e:
        if "xgboost" in model_config["model"]:
            raise ImportError(f"未安装XGBoost库，无法使用 xgb 模型: {model_config['model']}") from e
        raise ImportError(f"无法导入模型 {model_config['model']}: {e}") from e

    # 使用inspect检查构造函数的参数
    init_params = inspect.signature(ModelClass.__init__).parameters

    # 创建构造函数参数字典
    init_kwargs = {}
    if "random_state" in init_params:
        init_kwargs["random_state"] = random_state

    # 创建模型实例
    model = ModelClass(**init_kwargs)

    # 获取参数网格
    param_grid = model_config["grid"]

    # 创建两种格式的参数网格
    result = {
        "grid": param_grid,  # 列表形式，适用于GridSearchCV
        "random": {},  # 分布形式，适用于RandomizedSearchCV
    }

    # 为随机搜索创建分布形式的参数网格
    random_param_grid = {}
    for key, values in param_grid.items():
        if isinstance(values, list) and all(isinstance(v, int | float) for v in values if v is not None):
            numeric_values = [v for v in values if v is not None]
            if numeric_values:
                if all(isinstance(v, int) for v in numeric_values):
                    random_param_grid[key] = randint(min(numeric_values), max(numeric_values) + 1)
                else:
                    random_param_grid[key] = uniform(min(numeric_values), max(numeric_values) - min(numeric_values))
            else:
                # 对于None值列表，保持原样
                random_param_grid[key] = values
        else:
            # 非数值列表（如字符串选项）保持原样
            random_param_grid[key] = values

    result["random"] = random_param_grid

    return model, result


def _calculate_param_importance(search: GridSearchCV | RandomizedSearchCV) -> dict[str, float]:
    """计算参数重要性"""
    param_importance = {}

    # 获取所有参数组合
    params = search.cv_results_["params"]
    scores = search.cv_results_["mean_test_score"]

    # 对于每个超参数
    for param_name in search.best_params_:
        # 检查该参数是否有多个值
        param_values = set()
        for p in params:
            if param_name in p:
                param_values.add(str(p[param_name]))

        if len(param_values) <= 1:
            continue  # 跳过只有一个值的参数

        # 计算每个参数值的平均得分
        value_scores = {}
        value_counts = {}

        for i, p in enumerate(params):
            if param_name in p:
                value = str(p[param_name])
                if value not in value_scores:
                    value_scores[value] = 0
                    value_counts[value] = 0
                value_scores[value] += scores[i]
                value_counts[value] += 1

        # 计算平均得分
        for value in value_scores:
            value_scores[value] /= value_counts[value]

        # 参数重要性 = 最大平均得分 - 最小平均得分
        if value_scores:
            importance = max(value_scores.values()) - min(value_scores.values())
            param_importance[param_name] = importance

    # 归一化参数重要性
    if param_importance:
        max_importance = max(param_importance.values())
        if max_importance > 0:
            param_importance = {k: v / max_importance for k, v in param_importance.items()}

    # 按重要性排序
    param_importance = dict(sorted(param_importance.items(), key=lambda x: x[1], reverse=True))

    return param_importance  # noqa: RET504


def _create_param_importance_plot(param_importance: dict[str, float]) -> bytes:
    """创建参数重要性图表并返回字节数据"""
    plt.figure(figsize=(10, 6))

    # 获取按重要性排序的参数
    params = list(param_importance.keys())
    importances = list(param_importance.values())

    # 限制显示的参数数量，避免图表过于拥挤
    max_params = 15
    if len(params) > max_params:
        params = params[:max_params]
        importances = importances[:max_params]
        plt.title("超参数重要性 (显示前 15 个)")
    else:
        plt.title("超参数重要性")

    # 绘制条形图
    y_pos = np.arange(len(params))
    plt.barh(y_pos, importances, align="center")
    plt.yticks(y_pos, params)
    plt.xlabel("相对重要性")

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


class LearningCurveResult(TypedDict):
    """学习曲线结果类型"""

    train_sizes: list[int]
    train_scores_mean: list[float]
    train_scores_std: list[float]
    test_scores_mean: list[float]
    test_scores_std: list[float]
    message: str
    model_type: str
    score_metric: str


def plot_learning_curve(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    model_type: str = "random_forest",
    task_type: str = "auto",
    cv_folds: int = 5,
    scoring: str | None = None,
    train_sizes: list[float] | None = None,
    hyperparams: dict[str, Any] | None = None,
    random_state: int = 42,
) -> tuple[LearningCurveResult, bytes | None]:
    """
    生成并绘制学习曲线，评估模型性能随训练样本数量的变化。

    Args:
        df: 输入数据框
        features: 特征列名列表
        target: 目标变量列名
        model_type: 模型类型，同optimize_hyperparameters函数
        task_type: 任务类型，"regression"、"classification"或"auto"
        cv_folds: 交叉验证折数
        scoring: 评分指标
        train_sizes: 训练集大小的相对或绝对值，默认为[0.1, 0.3, 0.5, 0.7, 0.9]
        hyperparams: 模型超参数，为None时使用默认值
        random_state: 随机数种子

    Returns:
        LearningCurveResult: 学习曲线结果
        bytes | None: 学习曲线图表数据
    """
    # 验证输入参数
    if not all(f in df.columns for f in features):
        missing = set(features) - set(df.columns)
        raise ValueError(f"特征列表中包含不存在的列: {', '.join(missing)}")

    if target not in df.columns:
        raise ValueError(f"目标列 '{target}' 不存在于数据中")

    X = df[features].copy()
    y = df[target].copy()

    # 自动检测任务类型
    if task_type == "auto":
        if y.dtype == "object" or y.dtype == "category" or len(y.unique()) < 10:
            task_type = "classification"
            logger.info(f"自动检测到分类任务，目标列: {target}")
        else:
            task_type = "regression"
            logger.info(f"自动检测到回归任务，目标列: {target}")

    # 选择评分指标
    if scoring is None:
        scoring = "r2" if task_type == "regression" else "accuracy"

    # 获取模型
    model, _ = _get_model_and_param_grid(model_type, task_type, random_state)

    # 应用超参数
    if hyperparams:
        model.set_params(**hyperparams)

    # 设置训练集大小
    if train_sizes is None:
        train_sizes = [0.1, 0.3, 0.5, 0.7, 0.9]

    # 生成学习曲线
    logger.info(f"开始生成 {model_type} 模型的学习曲线...")
    train_sizes_abs, train_scores, test_scores = learning_curve(  # type:ignore
        model,
        X,
        y,
        train_sizes=train_sizes,  # type:ignore
        cv=cv_folds,
        scoring=scoring,
        n_jobs=-1,
        random_state=random_state,
    )

    # 计算平均值和标准差
    train_scores_mean = np.mean(train_scores, axis=1).tolist()
    train_scores_std = np.std(train_scores, axis=1).tolist()
    test_scores_mean = np.mean(test_scores, axis=1).tolist()
    test_scores_std = np.std(test_scores, axis=1).tolist()

    # 创建结果
    result = LearningCurveResult(
        train_sizes=train_sizes_abs.tolist(),
        train_scores_mean=train_scores_mean,
        train_scores_std=train_scores_std,
        test_scores_mean=test_scores_mean,
        test_scores_std=test_scores_std,
        message=f"生成了 {model_type} 模型的学习曲线",
        model_type=model_type,
        score_metric=scoring,
    )

    plt.figure(figsize=(10, 6))
    plt.title("学习曲线 (" + model_type + ")")
    plt.xlabel("训练样本数")
    plt.ylabel("得分 (" + str(scoring) + ")")
    plt.grid()

    plt.fill_between(
        train_sizes_abs,
        np.array(train_scores_mean) - np.array(train_scores_std),
        np.array(train_scores_mean) + np.array(train_scores_std),
        alpha=0.1,
        color="r",
    )
    plt.fill_between(
        train_sizes_abs,
        np.array(test_scores_mean) - np.array(test_scores_std),
        np.array(test_scores_mean) + np.array(test_scores_std),
        alpha=0.1,
        color="g",
    )
    plt.plot(train_sizes_abs, train_scores_mean, "o-", color="r", label="训练集得分")
    plt.plot(train_sizes_abs, test_scores_mean, "o-", color="g", label="验证集得分")

    plt.legend(loc="best")

    # 确保中文正确显示
    for text in plt.gca().get_xticklabels() + plt.gca().get_yticklabels():
        text.set_fontproperties(FontProperties(family=plt.rcParams["font.family"]))

    for item in [plt.gca().title, plt.gca().xaxis.label, plt.gca().yaxis.label]:
        if item:
            item.set_fontproperties(FontProperties(family=plt.rcParams["font.family"]))

    for text in plt.gca().legend().get_texts():
        text.set_fontproperties(FontProperties(family=plt.rcParams["font.family"]))

    plt.tight_layout()

    # 将图表保存为字节数据
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
    plt.close()
    buffer.seek(0)

    logger.info("学习曲线生成完成")
    return result, buffer.getvalue()
