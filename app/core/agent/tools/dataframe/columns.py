from typing import Any, Literal, NotRequired, TypedDict

import numpy as np
import pandas as pd

from app.core.agent.schemas import DatasetID, OperationFailed
from app.core.agent.sources import Sources
from app.log import logger
from app.utils import escape_tag

type SourceDatasets = dict[str, DatasetID]  # 变量名到数据集ID的映射


def ensure_datasets(sources: Sources, source_datasets: SourceDatasets) -> dict[str, pd.DataFrame]:
    for alias in source_datasets:
        if not alias.isidentifier():
            raise ValueError(f"数据集别名 '{alias}' 不是有效的Python标识符。")

    return {
        alias: sources.read(dataset_id)  # 数据集不存在时抛出错误
        for alias, dataset_id in source_datasets.items()
    }


class CreateColumnResult(TypedDict):
    success: Literal[True]
    message: str
    target_dataset_id: DatasetID
    statistics: dict[str, Any]  # 包含新列的统计信息
    sample_values: list[Any]  # 新列的前5个样本值
    dtype: str  # 新列的数据类型
    description: str | None  # 可选的新列描述和用途


def create_column(
    sources: Sources,
    source_datasets: SourceDatasets,
    target_dataset_id: DatasetID,
    column_name: str,
    expression: str,
    description: str | None = None,
) -> CreateColumnResult | OperationFailed:
    """
    计算一个新列，但不修改原始DataFrame。
    允许使用Python表达式对现有列进行操作，创建复合变量。

    Args:
        sources (Sources): 数据源管理对象。
        source_datasets (dict[DatasetID, str]): 数据集ID到变量名的映射。
        target_dataset_id (DatasetID): 目标数据集ID，用于保存新列。
        column_name (str): 新列的名称
        expression (str): Python表达式，用于计算新列的值。
        description (str, optional): 新列的描述和用途，提高可解释性。

    Returns:
        tuple: 包含计算的Series和结果信息的元组。如果失败则Series为None。
    """
    logger.opt(colors=True).info(
        f"创建新列: <e>{escape_tag(column_name)}</>, "
        f"基于表达式: <y>{escape_tag(expression)}</>, "
        f"使用数据集: <c>{escape_tag(str(source_datasets))}</>, "
        f"目标数据集: <c>{escape_tag(target_dataset_id)}</>"
    )

    for alias in source_datasets:
        if not alias.isidentifier():
            raise ValueError(f"数据集别名 '{alias}' 不是有效的Python标识符。")

    source_vars = {
        alias: sources.read(dataset_id)  # 数据集不存在时抛出错误
        for alias, dataset_id in source_datasets.items()
    }

    try:
        # 准备本地变量环境
        local_vars: dict[str, Any] = source_vars | {"np": np, "pd": pd}

        # 执行表达式计算新列值
        new_values = eval(  # noqa: S307
            expression,
            {"__builtins__": {}},  # 禁用内建函数提高安全性
            local_vars,
        )

        # 将结果转换为Series（如果不是）
        new_series = pd.Series(new_values) if not isinstance(new_values, pd.Series) else new_values
        new_series.name = column_name

        # 保存新列到目标数据集
        sources.read(target_dataset_id)[column_name] = new_series

        # 返回结果
        return {
            "success": True,
            "message": f"成功创建新列 '{column_name}'",
            "target_dataset_id": target_dataset_id,
            "statistics": new_series.describe().to_dict(),
            "sample_values": new_series.head(5).tolist(),
            "dtype": str(new_series.dtype),
            "description": description,
        }

    except Exception as e:
        logger.opt(colors=True).exception(f"创建列 '<e>{escape_tag(column_name)}</>' 时出错")
        return {
            "success": False,
            "message": f"错误: {e}",
            "error_type": type(e).__name__,
        }


class CreateInteractionTermResult(TypedDict):
    success: Literal[True]
    message: str
    statistics: dict[str, Any]  # 包含新列的统计信息
    sample_values: list[Any]  # 新列的前5个样本值
    null_count: int  # 新列中的空值数量


def create_interaction_term(
    df: pd.DataFrame,
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
                              - "multiply": 相乘 (默认，如A*B)
                              - "add": 相加 (如A+B)
                              - "subtract": 相减 (如A-B)
                              - "divide": 相除 (如A/B)
                              - "log_multiply": 取对数后相乘 (如log(A)*log(B))
        scale (bool): 是否对结果进行标准化缩放(均值0,标准差1)。

    Returns:
        dict: 包含操作结果的字典。
    """
    logger.opt(colors=True).info(
        f"创建交互项: <e>{escape_tag(column_name)}</>, "
        f"基于列: <c>{escape_tag(str(columns_to_interact))}</>, "
        f"交互方式: <y>{escape_tag(interaction_type)}</>"
    )

    try:
        if len(columns_to_interact) < 2:
            return {
                "success": False,
                "message": "错误: 至少需要两列进行交互。",
            }

        # 检查所有列是否存在
        missing_columns = [col for col in columns_to_interact if col not in df.columns]
        if missing_columns:
            return {
                "success": False,
                "message": f"错误: 以下列不存在: {', '.join(missing_columns)}",
            }

        # 检查所有列是否为数值类型
        non_numeric_columns = [col for col in columns_to_interact if not pd.api.types.is_numeric_dtype(df[col])]
        if non_numeric_columns:
            return {
                "success": False,
                "message": f"错误: 以下列不是数值型: {', '.join(non_numeric_columns)}",
            }

        # 创建交互项
        match interaction_type:
            case "multiply":
                result_series = df[columns_to_interact[0]].copy()
                for col in columns_to_interact[1:]:
                    result_series *= df[col]

            case "add":
                result_series = df[columns_to_interact[0]].copy()
                for col in columns_to_interact[1:]:
                    result_series += df[col]

            case "subtract":
                if len(columns_to_interact) != 2:
                    return {
                        "success": False,
                        "message": "错误: 'subtract' 交互类型只支持两列。",
                    }
                result_series = df[columns_to_interact[0]] - df[columns_to_interact[1]]

            case "divide":
                if len(columns_to_interact) != 2:
                    return {
                        "success": False,
                        "message": "错误: 'divide' 交互类型只支持两列。",
                    }
                # 防止除以零
                denominator = df[columns_to_interact[1]].copy()
                denominator = denominator.replace(0, np.nan)
                result_series = df[columns_to_interact[0]] / denominator

            case "log_multiply":
                # 处理负值和零值
                result_series = np.log(df[columns_to_interact[0]].clip(min=1e-10))
                for col in columns_to_interact[1:]:
                    result_series *= np.log(df[col].clip(min=1e-10))

            case _:
                return {
                    "success": False,
                    "message": f"错误: 不支持的交互类型 '{interaction_type}'。",
                }

        # 标准化
        if scale:
            result_series = (result_series - result_series.mean()) / result_series.std()

        # 保存到DataFrame
        df[column_name] = result_series

        # 生成结果
        stats = df[column_name].describe().to_dict()

        # 返回结果
        return {
            "success": True,
            "message": f"成功创建交互项 '{column_name}'",
            "statistics": stats,
            "sample_values": df[column_name].head(5).tolist(),
            "null_count": df[column_name].isna().sum(),
        }

    except Exception as e:
        logger.opt(colors=True).exception(f"创建交互项 '<b>{escape_tag(column_name)}</>' 时出错")
        return {"success": False, "message": f"错误: {e}"}


class CreateAggregatedFeatureResult(TypedDict):
    success: Literal[True]
    message: str
    statistics: dict[str, Any]  # 包含新列的统计信息
    sample_values: list[Any]  # 新列的前5个样本值
    unique_groups: int  # 分组的唯一数量
    group_sample_stats: dict[str, Any]  # 分组统计信息
    description: NotRequired[str]  # 可选的新列描述和用途


def create_aggregated_feature(
    df: pd.DataFrame,
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
    logger.opt(colors=True).info(
        f"创建聚合特征: <b>{escape_tag(column_name)}</b>, "
        f"基于分组: <c>{escape_tag(group_by_column)}</c>, "
        f"目标列: <c>{escape_tag(target_column)}</c>，聚合方式: <y>{escape_tag(aggregation)}</y>"
    )

    try:
        # 验证列是否存在
        if group_by_column not in df.columns:
            return {"success": False, "message": f"错误: 分组列 '{group_by_column}' 不存在。"}
        if target_column not in df.columns:
            return {"success": False, "message": f"错误: 目标列 '{target_column}' 不存在。"}

        # 验证目标列是否为数值类型(对于大多数聚合函数)
        if aggregation not in ["count", "nunique"] and not pd.api.types.is_numeric_dtype(df[target_column]):
            return {
                "success": False,
                "message": f"错误: 对于聚合方式 '{aggregation}'，目标列必须是数值型。",
            }

        # 执行聚合操作
        match aggregation:
            case "mean":
                agg_values = df.groupby(group_by_column)[target_column].transform("mean")
            case "median":
                agg_values = df.groupby(group_by_column)[target_column].transform("median")
            case "sum":
                agg_values = df.groupby(group_by_column)[target_column].transform("sum")
            case "min":
                agg_values = df.groupby(group_by_column)[target_column].transform("min")
            case "max":
                agg_values = df.groupby(group_by_column)[target_column].transform("max")
            case "std":
                agg_values = df.groupby(group_by_column)[target_column].transform("std")
            case "count":
                agg_values = df.groupby(group_by_column)[target_column].transform("count")
            case "nunique":
                # nunique不能直接使用transform，需要特殊处理
                unique_counts = df.groupby(group_by_column)[target_column].nunique()
                agg_values = df[group_by_column].map(unique_counts)  # type:ignore
            case _:
                return {"success": False, "message": f"错误: 不支持的聚合方式 '{aggregation}'。"}

        # 保存到DataFrame
        df[column_name] = agg_values

        # 生成结果
        stats = df[column_name].describe().to_dict()

        # 组间差异分析
        unique_groups = df[group_by_column].nunique()
        group_stats = df.groupby(group_by_column)[column_name].agg(["mean", "min", "max"]).head(5).to_dict()

        # 返回结果
        result: CreateAggregatedFeatureResult = {
            "success": True,
            "message": f"成功创建聚合特征 '{column_name}'",
            "statistics": stats,
            "sample_values": df[column_name].head(5).tolist(),
            "unique_groups": int(unique_groups),
            "group_sample_stats": group_stats,
        }

        if description:
            result["description"] = description

        return result

    except Exception as e:
        logger.opt(colors=True).exception(f"创建聚合特征 '<e>{escape_tag(column_name)}</>' 时出错")
        return {"success": False, "message": f"错误: {e}"}
