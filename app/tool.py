import pandas as pd
from scipy.stats import pearsonr, spearmanr
import numpy as np
import io
import base64
import matplotlib.pyplot as plt
import seaborn as sns
import joblib # 用于模型保存
import json 

# 机器学习模型
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.preprocessing import LabelEncoder # 用于处理分类目标的编码

# 注意：这里不再导入 @tool 装饰器或 Tool 类，因为这些是核心逻辑函数，
# 它们将在 test_langgraph.py 中被包装成 LangChain 工具。

def corr_analys(df: pd.DataFrame, col1: str, col2: str, method: str = "pearson"):
    """
    执行两个指定列之间的相关性分析。
    支持 Pearson (默认) 和 Spearman 方法。
    
    Args:
        df (pd.DataFrame): 输入的DataFrame。
        col1 (str): 第一个要分析的列名。
        col2 (str): 第二个要分析的列名。
        method (str): 相关性计算方法，可以是 'pearson' 或 'spearman'。

    Returns:
        dict: 包含相关系数和p值的结果字典。
    """
    # 相关性检测，增强健壮性
    # 检查列是否存在
    if col1 not in df.columns or col2 not in df.columns:
        raise ValueError(f"列 {col1} 或 {col2} 不存在")

    # 转为数值型，非数值型自动转为NaN
    x = pd.to_numeric(df[col1], errors="coerce")
    y = pd.to_numeric(df[col2], errors="coerce")

    # 检查有效数据量
    valid = x.notna() & y.notna()
    if valid.sum() < 3:
        raise ValueError(f"用于相关性分析的有效数据太少（仅{valid.sum()}行）")

    x = x[valid]
    y = y[valid]

    if method == "pearson":
        corr, p = pearsonr(x, y)
    else:
        corr, p = spearmanr(x, y)
    return {"correlation": corr, "p_value": p}

def lag_analys(df: pd.DataFrame, time_col1: str, time_col2: str):
    """
    计算两个时间字段之间的时滞（单位：秒），并返回分布统计、异常点等信息。
    
    Args:
        df (pd.DataFrame): 输入的DataFrame。
        time_col1 (str): 第一个时间列的名称。
        time_col2 (str): 第二个时间列的名称。

    Returns:
        dict: 包含平均时滞、最大时滞、最小时滞、标准差、时滞异常点和时滞分布描述的结果字典。
    """
    # 转换为datetime
    t1 = pd.to_datetime(df[time_col1])
    t2 = pd.to_datetime(df[time_col2])
    lag = (t2 - t1).dt.total_seconds()
    result = {
        "mean_lag_seconds": lag.mean(),
        "max_lag_seconds": lag.max(),
        "min_lag_seconds": lag.min(),
        "std_lag_seconds": lag.std(),
        "lag_outliers": df[(lag > lag.mean() + 3 * lag.std()) | (lag < lag.mean() - 3 * lag.std())][[time_col1, time_col2]].to_dict(orient="records"),
        "lag_distribution": lag.describe().to_dict()
    }
    return result

def detect_outliers(df: pd.DataFrame, column: str, method: str = "zscore", threshold: int = 3):
    """
    在指定列中检测异常值。
    支持 'zscore' (默认) 和 'iqr' 方法。

    Args:
        df (pd.DataFrame): 输入的DataFrame。
        column (str): 要检测异常值的列名。
        method (str): 异常值检测方法，可以是 'zscore' 或 'iqr'。
        threshold (int): 检测阈值。对于zscore，是标准差倍数；对于iqr，是IQR倍数。

    Returns:
        pd.DataFrame: 包含检测到的异常值的DataFrame。
    """
    # 只对数值型列做异常值检测
    if column not in df.columns:
        raise ValueError(f"列 {column} 不存在")
    series = pd.to_numeric(df[column], errors="coerce")
    if method == "zscore":
        mean = series.mean()
        std = series.std()
        mask = (np.abs(series - mean) > threshold * std)
    elif method == "iqr":
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        mask = (series < q1 - threshold * iqr) | (series > q3 + threshold * iqr)
    else:
        raise ValueError("不支持的异常值检测方法")
    return df[mask]

def train_model(df: pd.DataFrame, features: list[str], target: str, model_type: str = "linear_regression", test_size: float = 0.2, random_state: int = 42):
    """
    训练机器学习模型。
    支持 'linear_regression', 'decision_tree_regressor', 'random_forest_regressor' (回归任务)。
    自动处理目标变量为非数值的情况（分类任务）。
    
    Args:
        df (pd.DataFrame): 输入的DataFrame。
        features (list[str]): 特征列的名称列表。
        target (str): 目标列的名称。
        model_type (str): 模型类型，可选值包括 'linear_regression', 'decision_tree_regressor', 'random_forest_regressor', 'decision_tree_classifier', 'random_forest_classifier'。
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
    if Y.dtype == 'object' or Y.dtype == 'category':
        le = LabelEncoder()
        Y = le.fit_transform(Y)
        print(f"目标变量 '{target}' 已进行标签编码。原始类别: {le.classes_}")

    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=test_size, random_state=random_state)

    model = None
    if model_type == "linear_regression":
        model = LinearRegression()
        print("使用线性回归模型进行训练")
    elif model_type == "decision_tree_regressor":
        model = DecisionTreeRegressor(random_state=random_state)
        print("使用决策树回归模型进行训练")
    elif model_type == "random_forest_regressor":
        model = RandomForestRegressor(random_state=random_state)
        print("使用随机森林回归模型进行训练")
    elif model_type == "decision_tree_classifier": # 新增分类器
        model = DecisionTreeClassifier(random_state=random_state)
        print("使用决策树分类模型进行训练")
    elif model_type == "random_forest_classifier": # 新增分类器
        model = RandomForestClassifier(random_state=random_state)
        print("使用随机森林分类模型进行训练")
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
        "label_encoder": le # 保存编码器
    }

def evaluate_model(trained_model_info: dict):
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
    y_test = trained_model_info["Y_test"] # 修正键名
    model_type = trained_model_info["model_type"]

    y_pred = model.predict(X_test)

    metrics = {}
    message = ""

    # 根据模型类型选择评估指标
    if "regressor" in model_type: # 回归任务
        metrics["mean_squared_error"] = mean_squared_error(y_test, y_pred)
        metrics["r2_score"] = r2_score(y_test, y_pred)
        message = "模型评估完成 (回归任务)。"
    elif "classifier" in model_type: # 分类任务
        # 如果目标变量被编码过，需要将预测结果也转换为整数
        if trained_model_info.get("label_encoder") is not None:
            # 对于分类模型，y_pred通常是类别索引，但如果模型输出是概率，可能需要argmax
            if hasattr(model, 'predict_classes'): # scikit-learn的旧版本API
                 y_pred_classes = model.predict_classes(X_test)
            elif hasattr(model, 'predict_proba') and len(model.classes_) > 2: # 多分类
                 y_pred_classes = np.argmax(model.predict_proba(X_test), axis=1)
            else: # 二分类或直接输出类别
                 y_pred_classes = y_pred.astype(int) # 确保是整数类型
            
            # y_test也可能需要确保是整数类型，如果之前被编码
            y_test_classes = y_test.astype(int)

            metrics["accuracy"] = accuracy_score(y_test_classes, y_pred_classes)
            metrics["precision"] = precision_score(y_test_classes, y_pred_classes, average='weighted', zero_division=0)
            metrics["recall"] = recall_score(y_test_classes, y_pred_classes, average='weighted', zero_division=0)
            metrics["f1_score"] = f1_score(y_test_classes, y_pred_classes, average='weighted', zero_division=0)
            cm = confusion_matrix(y_test_classes, y_pred_classes)
            metrics["confusion_matrix"] = cm.tolist()
            message = "模型评估完成 (分类任务)。"

            le = trained_model_info["label_encoder"]
            y_pred_decoded = le.inverse_transform(y_pred_classes)
            y_test_decoded = le.inverse_transform(y_test_classes)
            message += f"\n预测类别示例 (解码后): {y_pred_decoded[:5].tolist()}"
            message += f"\n真实类别示例 (解码后): {y_test_decoded[:5].tolist()}"
        else: # 没有编码器，直接评估（假设y_test和y_pred已经是可比较的）
            metrics["accuracy"] = accuracy_score(y_test, y_pred)
            metrics["precision"] = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            metrics["recall"] = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            metrics["f1_score"] = f1_score(y_test, y_pred, average='weighted', zero_division=0)
            cm = confusion_matrix(y_test, y_pred)
            metrics["confusion_matrix"] = cm.tolist()
            message = "模型评估完成 (分类任务)。"
    else:
        message = f"不支持的模型类型 '{model_type}' 进行评估。"

    return {
        "metrics": metrics,
        "message": message,
        "predictions_summary": pd.Series(y_pred).describe().to_dict() # 预测结果的描述性统计
    }


def save_model(model_info: dict, file_path: str = "trained_model.joblib"):
    """
    保存训练好的机器学习模型及其元数据。
    
    Args:
        model_info (dict): 包含训练好的模型及其信息的字典，由 `train_model` 函数返回。
        file_path (str): 模型保存的路径，默认为 "trained_model.joblib"。

    Returns:
        dict: 包含保存结果消息和文件路径的字典。
    """
    model = model_info["model"]
    try:
        joblib.dump(model, file_path)
        # 还可以保存模型的元数据，例如特征列表、目标列、编码器等
        meta_data = {
            "model_type": model_info["model_type"],
            "feature_columns": model_info["feature_columns"],
            "target_column": model_info["target_column"],
        }
        # 如果有标签编码器，也保存它的类别信息
        if model_info.get("label_encoder") is not None:
            meta_data["label_encoder_classes"] = model_info["label_encoder"].classes_.tolist()


        with open(file_path + ".metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=4)

        return {"message": f"模型成功保存到 {file_path} 和 {file_path}.metadata.json", "file_path": file_path}
    except Exception as e:
        return {"message": f"保存模型失败: {e}"}
    

from langchain_core.tools import tool, Tool
class DataFrameTools:
        def __init__(self, df: pd.DataFrame):
            self.df = df

        @tool
        def correlation_analysis_tool(self, col1: str, col2: str, method: str = "pearson"):
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
            # 调用 tool.py 中定义的 corr_analys 函数，并传入内部保存的 self.df
            return corr_analys(self.df, col1, col2, method)

        @tool
        def lag_analysis_tool(self, time_col1: str, time_col2: str):
            """
            计算两个时间字段之间的时滞（单位：秒），并返回分布统计、异常点等信息。
            
            Args:
                time_col1 (str): 第一个时间列的名称。
                time_col2 (str): 第二个时间列的名称。

            Returns:
                dict: 包含平均时滞、最大时滞、最小时滞、标准差、时滞异常点和时滞分布描述的结果字典。
            """
            return lag_analys(self.df, time_col1, time_col2)

        @tool
        def detect_outliers_tool(self, column: str, method: str = "zscore", threshold: int = 3):
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
            return detect_outliers(self.df, column, method, threshold)

        @tool
        def train_model_tool(self, features: list[str], target: str, model_type: str = "linear_regression", test_size: float = 0.2, random_state: int = 42):
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
                dict: 包含训练好的模型、测试集数据、模型类型及相关信息的字典。
            """
            return train_model(self.df, features, target, model_type, test_size, random_state)

        @tool
        def evaluate_model_tool(self, trained_model_info: dict):
            """
            评估训练好的机器学习模型。
            接受 train_model_tool 函数的返回值作为输入。
            
            Args:
                trained_model_info (dict): 包含训练好的模型和测试集数据的字典，由 `train_model_tool` 函数返回。

            Returns:
                dict: 包含模型评估指标、消息和预测结果摘要的字典。
            """
            # 注意：evaluate_model 内部会用到模型和测试集，这些都在 trained_model_info 中
            return evaluate_model(trained_model_info)

        @tool
        def save_model_tool(self, model_info: dict, file_path: str = "trained_model.joblib"):
            """
            保存训练好的机器学习模型及其元数据。
            
            Args:
                model_info (dict): 包含训练好的模型及其信息的字典，由 `train_model_tool` 函数返回。
                file_path (str): 模型保存的路径。

            Returns:
                dict: 包含保存结果消息和文件路径的字典。
            """
            return save_model(model_info, file_path)