from typing import Any

import pandas as pd
from langchain_core.tools import BaseTool, tool

from app.core.agent.schemas import DatasetCreator, DatasetGetter, DatasetID, OperationFailed
from app.log import logger
from app.utils import escape_tag

from .analysis import corr_analys, detect_outliers, lag_analys
from .columns import (
    CreateAggregatedFeatureResult,
    CreateColumnResult,
    CreateInteractionTermResult,
    create_aggregated_feature,
    create_column,
    create_interaction_term,
)
from .inspect import InspectDataframeOptions, InspectDataframeResult, inspect_dataframe
from .missing_values import (
    HandleMissingValuesResult,
    MissingValuesSummary,
    get_missing_values_summary,
    handle_missing_values,
)
from .multi import (
    CombineDataframesOperation,
    CombineDataframesResult,
    CreateDatasetResult,
    JoinDataframesResult,
    JoinType,
    combine_dataframes,
    create_dataset_by_sampling,
    create_dataset_from_query,
    join_dataframes,
)


def dataframe_tools(get_df: DatasetGetter, create_df: DatasetCreator) -> list[BaseTool]:
    @tool
    def correlation_analysis_tool(
        dataset_id: DatasetID,
        col1: str,
        col2: str,
        method: str = "pearson",
    ) -> dict[str, Any]:
        """
        执行两个指定列之间的相关性分析。
        支持 Pearson (默认) 和 Spearman 方法。

        Args:
            dataset_id (str): 操作的数据集ID。
            col1 (str): 第一个要分析的列名。
            col2 (str): 第二个要分析的列名。
            method (str): 相关性计算方法，可以是 'pearson' 或 'spearman'。

        Returns:
            dict: 包含相关系数和p值的结果字典。
        """
        logger.opt(colors=True).info(
            f"执行<g>相关性分析</>: <y>{escape_tag(col1)}</> 与 <y>{escape_tag(col2)}</>, 方法: {escape_tag(method)}"
        )
        return corr_analys(get_df(dataset_id), col1, col2, method)

    @tool
    def lag_analysis_tool(
        dataset_id: DatasetID,
        time_col1: str,
        time_col2: str,
    ) -> dict[str, Any]:
        """
        计算两个时间字段之间的时滞（单位：秒），并返回分布统计、异常点等信息。

        Args:
            dataset_id (str): 操作的数据集ID。
            time_col1 (str): 第一个时间列的名称。
            time_col2 (str): 第二个时间列的名称。

        Returns:
            dict: 包含平均时滞、最大时滞、最小时滞、标准差、时滞异常点和时滞分布描述的结果字典。
        """
        logger.opt(colors=True).info(
            f"执行<g>时滞分析</>: <y>{escape_tag(time_col1)}</> 与 <y>{escape_tag(time_col2)}</>"
        )
        return lag_analys(get_df(dataset_id), time_col1, time_col2)

    @tool
    def detect_outliers_tool(
        dataset_id: DatasetID,
        column: str,
        method: str = "zscore",
        threshold: int = 3,
    ) -> pd.DataFrame:
        """
        在指定列中检测异常值。
        支持 'zscore' (默认) 和 'iqr' 方法。

        Args:
            dataset_id (str): 操作的数据集ID。
            column (str): 要检测异常值的列名。
            method (str): 异常值检测方法，可以是 'zscore' 或 'iqr'。
            threshold (int): 检测阈值。对于zscore，是标准差倍数；对于iqr，是IQR倍数。

        Returns:
            pd.DataFrame: 包含检测到的异常值的DataFrame。
        """
        logger.opt(colors=True).info(
            f"<g>检测异常值</>: "
            f"列 <y>{escape_tag(column)}</>, "
            f"方法: <y>{escape_tag(method)}</>, "
            f"阈值: <y>{threshold}</>"
        )
        return detect_outliers(get_df(dataset_id), column, method, threshold)

    @tool
    def create_column_tool(
        dataset_id: DatasetID,
        column_name: str,
        expression: str,
        columns_used: list[str] | None = None,
        description: str | None = None,
    ) -> CreateColumnResult | OperationFailed:
        """
        可以使用此工具修改现有列或创建新列（包括简单的数据清洗）
        允许使用Python表达式对现有列进行操作，创建复合变量。

        Args:
            dataset_id (str): 操作的数据集ID。
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
        return create_column(get_df(dataset_id), column_name, expression, columns_used, description)

    @tool
    def create_interaction_term_tool(
        dataset_id: DatasetID,
        column_name: str,
        columns_to_interact: list[str],
        interaction_type: str = "multiply",
        scale: bool = False,
    ) -> CreateInteractionTermResult | OperationFailed:
        """
        创建交互项作为新列，用于捕捉特征间的相互作用效应。

        Args:
            dataset_id (str): 操作的数据集ID。
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
        return create_interaction_term(get_df(dataset_id), column_name, columns_to_interact, interaction_type, scale)

    @tool
    def create_aggregated_feature_tool(
        dataset_id: DatasetID,
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
            dataset_id (str): 操作的数据集ID。
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
        return create_aggregated_feature(
            get_df(dataset_id), column_name, group_by_column, target_column, aggregation, description
        )

    @tool
    def inspect_dataframe_tool(
        dataset_id: DatasetID,
        options: InspectDataframeOptions | None = None,
    ) -> InspectDataframeResult:
        """
        全面查看当前数据框的状态，包括数据结构、预览和统计摘要。
        这个工具特别适合在进行数据修改后使用，例如使用create_column_tool创建新列、
        或进行其他数据转换操作后，检查数据的最新状态。

        Args:
            dataset_id (str): 操作的数据集ID
            options (dict, optional): 查看选项，可包含：
                - show_columns (bool): 是否显示完整列列表，默认True
                - show_dtypes (bool): 是否显示每列的数据类型，默认True
                - show_null_counts (bool): 是否显示每列的空值数量，默认True
                - show_summary_stats (bool): 是否显示数值列的统计摘要，默认True
                - show_unique_counts (bool): 是否显示分类列唯一值数量，默认True
                - n_rows (int): 预览的行数，默认5
                - include_columns (list): 仅包含指定列
                - exclude_columns (list): 排除指定列

        Returns:
            dict: 包含数据框详细信息的结果
        """
        return inspect_dataframe(get_df(dataset_id), options)

    @tool
    def handle_missing_values_tool(
        dataset_id: DatasetID,
        column: str | None = None,
        method: str = "drop",
    ) -> HandleMissingValuesResult:
        """
        处理数据框中的缺失值

        Args:
            dataset_id (str): 操作的数据集ID
            column: 目标列名，如果为 None 则处理所有列
            method: 处理方法 ('drop', 'fill_mean', 'fill_median',
            'fill_mode', 'fill_forward', 'fill_backward', 'interpolate')

        Returns:
            处理结果字典
        """
        return handle_missing_values(get_df(dataset_id), column, method)

    @tool
    def get_missing_values_summary_tool(dataset_id: DatasetID) -> MissingValuesSummary:
        """
        获取缺失值摘要信息

        Args:
            dataset_id (str): 操作的数据集ID

        Returns:
            缺失值摘要字典
        """
        return get_missing_values_summary(get_df(dataset_id))

    @tool
    def join_dataframes_tool(
        left_dataset_id: DatasetID,
        right_dataset_id: DatasetID,
        join_type: JoinType = "inner",
        left_on: str | list[str] | None = None,
        right_on: str | list[str] | None = None,
    ) -> JoinDataframesResult | OperationFailed:
        """
        将两个数据框按指定列进行连接。

        Args:
            left_dataset_id (str): 左侧数据集ID
            right_dataset_id (str): 右侧数据集ID
            join_type (str): 连接类型，可选值：'inner', 'left', 'right', 'outer', 'cross'
            left_on (str | List[str], optional): 左侧数据框用于连接的列名(单个或列表)
            right_on (str | List[str], optional): 右侧数据框用于连接的列名(单个或列表)

        Returns:
            dict: 包含连接结果的字典。
        """
        result = join_dataframes(get_df(left_dataset_id), get_df(right_dataset_id), join_type, left_on, right_on)
        if result[0] is not None:
            source_id = create_df(result[0])
            result[1]["new_dataset_id"] = source_id

        return result[1]

    @tool
    def combine_dataframes_tool(
        dataset_ids: list[DatasetID],
        operation: CombineDataframesOperation = "union",
        match_columns: bool = True,
        ignore_index: bool = True,
    ) -> CombineDataframesResult | OperationFailed:
        """
        将多个数据框按指定列进行连接。

        Args:
            dataset_ids (List[str]): 数据集ID列表（至少需要1个）
            operation (str): 集合操作类型，可选值：
                - 'union': 合并所有数据框的行（保留所有行，类似SQL的UNION ALL）
                - 'intersection': 只保留在所有数据框中都出现的行
                - 'difference': 保留第一个数据框中不在其他数据框中出现的行
            match_columns (bool): 是否要求所有数据框的列完全匹配，默认为True
            ignore_index (bool): 是否重置结果数据框的索引，默认为True

        Returns:
            dict: 包含连接结果的字典。
        """
        result = combine_dataframes([get_df(id) for id in dataset_ids], operation, match_columns, ignore_index)

        if result[0] is not None:
            source_id = create_df(result[0])
            result[1]["new_dataset_id"] = source_id

        return result[1]

    @tool
    def create_dataset_from_query_tool(
        dataset_id: DatasetID,
        query: str,
        columns: list[str] | None = None,
        reset_index: bool = True,
    ) -> CreateDatasetResult | OperationFailed:
        """
        从现有数据集中创建一个新的数据集，基于指定的查询条件。

        Args:
            dataset_id (str): 源数据集ID
            query (str): 筛选条件，使用pandas query语法，如 "age > 30 and gender == 'F'"
            columns (list[str], optional): 要包含的列名列表，如果为None则包含所有列
            reset_index (bool): 是否重置结果数据集的索引，默认为True

        Returns:
            dict: 包含新数据集ID和样本数据的结果字典。
        """
        result = create_dataset_from_query(get_df(dataset_id), query, columns, reset_index)
        if result[0] is not None:
            source_id = create_df(result[0])
            result[1]["new_dataset_id"] = source_id

        return result[1]

    @tool
    def create_dataset_by_sampling_tool(
        dataset_id: DatasetID,
        n: int | None = None,
        frac: float | None = None,
        random_state: int | None = None,
        stratify_by: str | None = None,
    ) -> CreateDatasetResult | OperationFailed:
        """
        从现有数据集中创建一个新的数据集，基于随机采样。

        Args:
            dataset_id (str): 源数据集ID
            n (int, optional): 要采样的行数，与frac二选一
            frac (float, optional): 要采样的比例，如0.3表示采样30%的数据，与n二选一
            random_state (int, optional): 随机种子，用于可重现的结果
            stratify_by (str, optional): 分层采样的列名，确保采样结果保持该列的分布

        Returns:
            dict: 包含新数据集ID和样本数据的结果字典。
        """
        result = create_dataset_by_sampling(get_df(dataset_id), n, frac, random_state, stratify_by)
        if result[0] is not None:
            source_id = create_df(result[0])
            result[1]["new_dataset_id"] = source_id

        return result[1]

    return [
        # 数据检查/探索工具（了解数据）
        inspect_dataframe_tool,
        get_missing_values_summary_tool,
        handle_missing_values_tool,
        # 数据分析工具（分析数据特性）
        correlation_analysis_tool,
        detect_outliers_tool,
        lag_analysis_tool,
        # 数据转换工具（基于分析结果进行数据转换）
        create_column_tool,
        create_interaction_term_tool,
        create_aggregated_feature_tool,
        # 多数据集操作工具
        join_dataframes_tool,
        combine_dataframes_tool,
        create_dataset_from_query_tool,
        create_dataset_by_sampling_tool,
    ]


__all__ = ["dataframe_tools"]
