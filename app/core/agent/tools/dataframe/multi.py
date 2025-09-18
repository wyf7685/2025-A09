from typing import Any, Literal, TypedDict, cast

import pandas as pd
from sklearn.model_selection import train_test_split

from app.core.agent.schemas import DatasetID, OperationFailed
from app.core.agent.sources import Sources
from app.log import logger
from app.utils import escape_tag

type JoinType = Literal["inner", "left", "right", "outer", "cross"]


class JoinDataframesResult(TypedDict):
    """数据集连接操作的结果"""

    success: Literal[True]
    message: str  # 操作结果信息
    new_dataset_id: str  # 新创建的数据集ID
    shape: tuple[int, int]  # 新数据集的形状 (行数, 列数)
    columns: list[str]  # 新数据集的列名列表
    preview: str  # 新数据集的预览数据
    join_details: dict[str, Any]  # 连接操作的详情


def join_dataframes(
    sources: Sources,
    left_dataset_id: DatasetID,
    right_dataset_id: DatasetID,
    join_type: JoinType = "inner",
    left_on: str | list[str] | None = None,
    right_on: str | list[str] | None = None,
    new_dataset_id: DatasetID | None = None,
) -> JoinDataframesResult | OperationFailed:
    """
    连接两个数据框，创建新的数据集

    Args:
        sources (Sources): 数据源管理对象
        left_dataset_id (str): 左侧数据集ID
        right_dataset_id (str): 右侧数据集ID
        join_type (str): 连接类型，可选值：'inner', 'left', 'right', 'outer', 'cross'
        left_on (str | List[str], optional): 左侧数据框用于连接的列名(单个或列表)
        right_on (str | List[str], optional): 右侧数据框用于连接的列名(单个或列表)
        new_dataset_id (DatasetID | None): 可选参数，指定存储新数据框的数据集ID

    Returns:
        JoinDataframesResult | OperationFailed: 操作结果
    """
    df_left = sources.read(left_dataset_id)
    df_right = sources.read(right_dataset_id)

    try:
        # 验证连接类型
        valid_join_types = ["inner", "left", "right", "outer", "cross"]
        if join_type not in valid_join_types:
            return {
                "success": False,
                "message": f"不支持的连接类型: {join_type}，有效的连接类型有: {', '.join(valid_join_types)}",
                "error_type": "InvalidJoinType",
            }

        # 验证连接键
        if join_type != "cross" and (left_on is None or right_on is None):
            return {
                "success": False,
                "message": f"连接类型 '{join_type}' 需要指定 left_on 和 right_on 参数",
                "error_type": "MissingJoinKeys",
            }

        # 验证左侧连接列存在
        if left_on is not None:
            for col in [left_on] if isinstance(left_on, str) else left_on:
                if col not in df_left.columns:
                    return {
                        "success": False,
                        "message": f"左侧数据框中不存在列: {col}",
                        "error_type": "ColumnNotFound",
                    }

        # 验证右侧连接列存在
        if right_on is not None:
            for col in [right_on] if isinstance(right_on, str) else right_on:
                if col not in df_right.columns:
                    return {
                        "success": False,
                        "message": f"右侧数据框中不存在列: {col}",
                        "error_type": "ColumnNotFound",
                    }

        # 记录连接前的信息，用于结果报告
        left_shape = df_left.shape
        right_shape = df_right.shape

        # 执行连接操作
        logger.opt(colors=True).info(
            f"<g>连接数据框</>: "
            f"类型 <y>{join_type}</>, "
            f"左键 <y>{escape_tag(str(left_on))}</>, "
            f"右键 <y>{escape_tag(str(right_on))}</>"
        )

        if join_type == "cross":
            result_df = df_left.merge(df_right, how=join_type)
        else:
            result_df = df_left.merge(df_right, how=join_type, left_on=left_on, right_on=right_on)

        # 保存结果数据集
        dataset_id = sources.create(result_df, new_dataset_id, f"[连接自{left_dataset_id}和{right_dataset_id}的数据集]")

        # 生成结果
        join_details = {
            "left_shape": left_shape,
            "right_shape": right_shape,
            "result_shape": result_df.shape,
            "join_type": join_type,
            "left_on": left_on,
            "right_on": right_on,
            "common_columns_count": len(set(df_left.columns).intersection(set(df_right.columns))),
            "unique_columns_count": {
                "left": len(set(df_left.columns) - set(df_right.columns)),
                "right": len(set(df_right.columns) - set(df_left.columns)),
            },
        }

        return {
            "success": True,
            "message": f"成功创建连接数据集，包含 {result_df.shape[0]} 行和 {result_df.shape[1]} 列",
            "new_dataset_id": dataset_id,
            "shape": result_df.shape,
            "columns": result_df.columns.tolist(),
            "preview": result_df.head(5).to_string(),
            "join_details": join_details,
        }

    except Exception as e:
        logger.exception("连接数据框时发生错误")
        return {
            "success": False,
            "message": f"连接数据框时发生错误: {e}",
            "error_type": type(e).__name__,
        }


type CombineDataframesOperation = Literal["union", "intersection", "difference"]


class CombineDataframesResult(TypedDict):
    """数据集合并操作的结果"""

    success: Literal[True]
    message: str  # 操作结果信息
    new_dataset_id: str  # 新创建的数据集ID
    shape: tuple[int, int]  # 新数据集的形状 (行数, 列数)
    columns: list[str]  # 新数据集的列名列表
    preview: str  # 新数据集的预览数据
    combine_details: dict[str, Any]  # 合并操作的详情


def combine_dataframes(
    sources: Sources,
    dataset_ids: list[DatasetID],
    operation: CombineDataframesOperation = "union",
    match_columns: bool = True,
    ignore_index: bool = True,
    new_dataset_id: DatasetID | None = None,
) -> CombineDataframesResult | OperationFailed:
    """
    执行多个数据框之间的集合操作，创建新的数据集

    Args:
        sources (Sources): 数据源管理对象
        dataset_ids (list[str]): 数据集ID列表（至少需要1个）
        operation (str): 集合操作类型，可选值：
            - 'union': 合并所有数据框的行（保留所有行，类似SQL的UNION ALL）
            - 'intersection': 只保留在所有数据框中都出现的行
            - 'difference': 保留第一个数据框中不在其他数据框中出现的行
        match_columns (bool): 是否要求所有数据框的列完全匹配，默认为True
        ignore_index (bool): 是否重置结果数据框的索引，默认为True
        new_dataset_id (DatasetID | None): 可选参数，指定存储新数据框的数据集ID

    Returns:
        CombineDataframesResult | OperationFailed: 操作结果
    """
    dfs = [sources.read(id) for id in dataset_ids]

    # 基本验证
    if not dfs:
        return {
            "success": False,
            "message": "至少需要提供一个数据框",
            "error_type": "InvalidInput",
        }

    valid_operations = ["union", "intersection", "difference"]
    if operation not in valid_operations:
        return {
            "success": False,
            "message": f"不支持的操作类型: {operation}，有效的操作类型有: {', '.join(valid_operations)}",
            "error_type": "InvalidOperation",
        }

    # 检查列的一致性（如果要求匹配列）
    if match_columns and len(dfs) > 1:
        first_df_columns = set(dfs[0].columns)
        for i, df in enumerate(dfs[1:], 1):
            if set(df.columns) != first_df_columns:
                return {
                    "success": False,
                    "message": f"数据框 #{i} 的列与第一个数据框不匹配。"
                    "如果要合并具有不同列的数据框，请将match_columns参数设置为False",
                    "error_type": "ColumnMismatch",
                }

    # 记录合并前的信息，用于结果报告
    input_shapes = [df.shape for df in dfs]

    # 执行集合操作
    logger.opt(colors=True).info(f"<g>合并数据框</>: 操作 <y>{escape_tag(operation)}</>, 数据框数量 <y>{len(dfs)}</>")

    try:
        result_df = None
        if operation == "union":
            # 合并所有数据框（保留所有行）
            if match_columns:
                result_df = pd.concat(dfs, axis=0, ignore_index=ignore_index)
            else:
                # 如果不需要匹配列，则使用outer join方式连接
                result_df = pd.concat(dfs, axis=0, ignore_index=ignore_index, join="outer")

        elif operation == "intersection":
            # 只保留在所有数据框中都出现的行
            if len(dfs) == 1:
                result_df = dfs[0].copy()
            else:
                # 对于多个数据框，找出它们之间的交集
                common_rows = set(map(tuple, dfs[0].itertuples(index=False)))
                for df in dfs[1:]:
                    common_rows &= set(map(tuple, df.itertuples(index=False)))

                # 将结果转换回DataFrame
                if common_rows:
                    result_df = pd.DataFrame(list(common_rows), columns=dfs[0].columns)
                else:
                    result_df = pd.DataFrame(columns=dfs[0].columns)  # 空DataFrame，保持列名

        elif operation == "difference":
            # 保留第一个数据框中不在其他数据框中出现的行
            if len(dfs) == 1:
                result_df = dfs[0].copy()
            else:
                first_rows = set(map(tuple, dfs[0].itertuples(index=False)))
                other_rows = set()
                for df in dfs[1:]:
                    other_rows |= set(map(tuple, df.itertuples(index=False)))

                # 差集计算
                diff_rows = first_rows - other_rows

                # 将结果转换回DataFrame
                if diff_rows:
                    result_df = pd.DataFrame(list(diff_rows), columns=dfs[0].columns)
                else:
                    result_df = pd.DataFrame(columns=dfs[0].columns)  # 空DataFrame，保持列名

        # 保存结果数据集
        dataset_id = sources.create(result_df, new_dataset_id, f"[{operation}自{', '.join(dataset_ids)}的数据集]")

        # 生成结果
        combine_details = {
            "operation": operation,
            "input_shapes": input_shapes,
            "input_rows_total": sum(shape[0] for shape in input_shapes),
            "output_rows": result_df.shape[0],
            "match_columns": match_columns,
            "common_columns_count": len(set.intersection(*[set(df.columns) for df in dfs]))
            if len(dfs) > 1
            else len(dfs[0].columns),
        }

        return {
            "success": True,
            "message": f"成功执行{operation}操作，结果数据集包含 {result_df.shape[0]} 行和 {result_df.shape[1]} 列",
            "new_dataset_id": dataset_id,
            "shape": result_df.shape,
            "columns": result_df.columns.tolist(),
            "preview": result_df.head(5).to_string(),
            "combine_details": combine_details,
        }

    except Exception as e:
        logger.exception(f"执行数据框{operation}操作时发生错误")
        return {
            "success": False,
            "message": f"执行数据框{operation}操作时发生错误: {e}",
            "error_type": type(e).__name__,
        }


class CreateDatasetResult(TypedDict):
    """创建新数据集操作的结果"""

    success: Literal[True]
    message: str  # 操作结果信息
    new_dataset_id: str  # 新创建的数据集ID
    shape: tuple[int, int]  # 新数据集的形状 (行数, 列数)
    columns: list[str]  # 新数据集的列名列表
    preview: str  # 新数据集的预览数据
    creation_details: dict[str, Any]  # 创建操作的详情


def create_dataset_from_query(
    sources: Sources,
    dataset_id: DatasetID,
    query: str,
    columns: list[str] | None = None,
    reset_index: bool = True,
    new_dataset_id: DatasetID | None = None,
) -> CreateDatasetResult | OperationFailed:
    """
    通过查询条件从现有数据集创建新数据集

    Args:
        sources (Sources): 数据源管理对象
        dataset_id (str): 源数据集ID
        query (str): 筛选条件，使用pandas query语法，如 "age > 30 and gender == 'F'"
        columns (list[str], optional): 要包含的列名列表，如果为None则包含所有列
        reset_index (bool): 是否重置结果数据集的索引，默认为True
        new_dataset_id (DatasetID | None): 可选参数，指定存储新数据框的数据集ID

    Returns:
        CreateDatasetResult | OperationFailed: 操作结果
    """
    source_df = sources.read(dataset_id)

    # 验证列名
    if columns is not None:
        missing_columns = [col for col in columns if col not in source_df.columns]
        if missing_columns:
            return {
                "success": False,
                "message": f"源数据框中不存在以下列: {', '.join(missing_columns)}",
                "error_type": "ColumnNotFound",
            }

    # 记录源数据框信息
    source_shape = source_df.shape

    # 执行查询
    logger.opt(colors=True).info(f"<g>通过查询创建数据集</>: 查询 <y>{escape_tag(query)}</>")

    try:
        try:
            # 应用查询条件
            filtered_df = source_df.query(query)

            # 如果指定了列，则只保留这些列
            if columns is not None:
                filtered_df = cast("pd.DataFrame", filtered_df[columns])

            # 重置索引（如果需要）
            if reset_index:
                filtered_df = filtered_df.reset_index(drop=True)

        except Exception as e:
            return {
                "success": False,
                "message": f"查询时出现错误: {e}",
                "error_type": type(e).__name__,
            }

        # 保存结果数据集
        dataset_id = sources.create(filtered_df, new_dataset_id, f"[查询自{dataset_id}的数据集, 查询语句: {query}]")

        # 生成结果
        creation_details = {
            "source_shape": source_shape,
            "result_shape": filtered_df.shape,
            "query": query,
            "selected_columns": columns,
            "rows_selected": filtered_df.shape[0],
            "rows_filtered_out": source_shape[0] - filtered_df.shape[0],
        }

        return {
            "success": True,
            "message": f"成功创建查询数据集，包含 {filtered_df.shape[0]} 行和 {filtered_df.shape[1]} 列",
            "new_dataset_id": dataset_id,
            "shape": filtered_df.shape,
            "columns": filtered_df.columns.tolist(),
            "preview": filtered_df.head(5).to_string(),
            "creation_details": creation_details,
        }

    except Exception as e:
        logger.exception("通过查询创建数据集时发生错误")
        return {
            "success": False,
            "message": f"通过查询创建数据集时发生错误: {e}",
            "error_type": type(e).__name__,
        }


def create_dataset_by_sampling(
    sources: Sources,
    dataset_id: DatasetID,
    n: int | None = None,
    frac: float | None = None,
    random_state: int | None = None,
    stratify_by: str | None = None,
    new_dataset_id: DatasetID | None = None,
) -> CreateDatasetResult | OperationFailed:
    """
    通过采样从现有数据集创建新数据集

    Args:
        sources (Sources): 数据源管理对象
        dataset_id (str): 源数据集ID
        n (int, optional): 要采样的行数，与frac二选一
        frac (float, optional): 要采样的比例，如0.3表示采样30%的数据，与n二选一
        random_state (int, optional): 随机种子，用于可重现的结果
        stratify_by (str, optional): 分层采样的列名，确保采样结果保持该列的分布
        new_dataset_id (DatasetID | None): 可选参数，指定存储新数据框的数据集ID

    Returns:
        CreateDatasetResult | OperationFailed: 操作结果
    """
    source_df = sources.read(dataset_id)

    # 参数验证
    if n is None and frac is None:
        return {
            "success": False,
            "message": "必须指定n或frac参数之一",
            "error_type": "MissingParameter",
        }
    if n is not None and frac is not None:
        return {
            "success": False,
            "message": "n和frac参数不能同时指定",
            "error_type": "ConflictingParameters",
        }

    if frac is not None and (frac <= 0 or frac > 1):
        return {
            "success": False,
            "message": "frac参数必须在(0, 1]范围内",
            "error_type": "InvalidParameter",
        }

    if n is not None and (n <= 0 or n > len(source_df)):
        return {
            "success": False,
            "message": f"n参数必须在(0, {len(source_df)}]范围内",
            "error_type": "InvalidParameter",
        }

    # 验证分层采样列
    if stratify_by is not None and stratify_by not in source_df.columns:
        return {
            "success": False,
            "message": f"分层采样列 '{stratify_by}' 不存在",
            "error_type": "ColumnNotFound",
        }

    # 记录源数据框信息
    source_shape = source_df.shape

    # 执行采样
    sample_desc = f"{n}行" if n is not None or frac is None else f"{frac * 100:.1f}%"
    logger.opt(colors=True).info(
        f"<g>通过采样创建数据集</>: 采样 <y>{sample_desc}</>"
        + (f", 分层列 <y>{escape_tag(stratify_by)}</>" if stratify_by else "")
    )

    try:
        if stratify_by:
            # 分层采样
            y = source_df[stratify_by]

            # 确定采样比例
            if n is not None:
                # 计算等效的比例
                frac = n / len(source_df)

            # 进行采样
            sampled_df, _ = train_test_split(source_df, train_size=frac, random_state=random_state, stratify=y)
            sampled_df = cast("pd.DataFrame", sampled_df).reset_index(drop=True)
        else:
            # 简单随机采样
            sample_kwargs: dict[str, Any] = {"random_state": random_state}
            if n is not None:
                sample_kwargs["n"] = n
            else:
                sample_kwargs["frac"] = frac

            sampled_df = source_df.sample(**sample_kwargs).reset_index(drop=True)

        # 保存结果数据集
        dataset_id = sources.create(sampled_df, new_dataset_id, f"[采样自{dataset_id}的数据集, 采样: {sample_desc}]")

        # 生成结果
        creation_details = {
            "source_shape": source_shape,
            "result_shape": sampled_df.shape,
            "sampling_method": "stratified" if stratify_by else "random",
            "sample_size": n if n is not None else None,
            "sample_fraction": frac if frac is not None else (n / len(source_df) if n is not None else None),
            "stratify_by": stratify_by,
            "random_state": random_state,
        }

        return {
            "success": True,
            "message": f"成功创建采样数据集，包含 {sampled_df.shape[0]} 行和 {sampled_df.shape[1]} 列",
            "new_dataset_id": dataset_id,
            "shape": sampled_df.shape,
            "columns": sampled_df.columns.tolist(),
            "preview": sampled_df.head(5).to_string(),
            "creation_details": creation_details,
        }

    except Exception as e:
        logger.exception("通过采样创建数据集时发生错误")
        return {
            "success": False,
            "message": f"通过采样创建数据集时发生错误: {e}",
            "error_type": type(e).__name__,
        }
