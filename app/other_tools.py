import pandas as pd
from langchain_core.tools import tool, Tool,BaseTool

# 导入 tool.py 中的核心逻辑函数
from app.tool import corr_analys, lag_analys, detect_outliers, train_model, evaluate_model, save_model

def create_dataframe_tools(df: pd.DataFrame) -> list[BaseTool]:
    """
    创建一个包含多种数据帧操作工具的列表。
    这些工具通过封装 DataFrame 实例，避免了直接在工具签名中暴露 pd.DataFrame 参数。

    Args:
        df (pd.DataFrame): 要用于数据分析的 DataFrame。

    Returns:
        list[Tool]: 包含所有数据帧操作工具的列表。
    """
    class DataFrameTools:
        """
        封装 DataFrame 的类，其方法作为 LangChain 工具使用。
        """
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

    # 实例化工具类，将 df 绑定到类实例中
    df_tools_instance = DataFrameTools(df)
    
    # 收集所有 LangChain 工具对象
    return [
        df_tools_instance.correlation_analysis_tool,
        df_tools_instance.lag_analysis_tool,
        df_tools_instance.detect_outliers_tool,
        df_tools_instance.train_model_tool,
        df_tools_instance.evaluate_model_tool,
        df_tools_instance.save_model_tool,
    ]