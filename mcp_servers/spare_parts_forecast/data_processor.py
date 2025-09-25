"""
备件数据处理器

提供数据转换和预处理功能，支持从CSV文件读取备件领用记录，
进行数据透视、分类和统计分析。
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def transferdata_try() -> pd.DataFrame:
    """
    转换数据格式，从原始CSV文件生成透视表

    Returns:
        处理后的数据透视表DataFrame
    """
    # 读取CSV文件
    # df = pd.read_csv("备品备件库存移动清单查询.csv", encoding="utf-8")
    df = pd.read_csv("2018-2023年备件领用记录.csv", encoding="utf-8")
    # df = pd.read_csv("杭州领用记录.csv", encoding="utf-8")
    # df = pd.read_csv("宁波领用记录.csv", encoding="utf-8")
    # 将日期列转换为日期时间格式
    df["凭证日期"] = pd.to_datetime(df["凭证日期"], format="%Y%m%d")
    # df['凭证日期'] = pd.to_datetime(df['凭证日期'], format='%Y/%m/%d')
    # df['凭证日期'] = pd.to_datetime(df['凭证日期'], format='%Y-%m-%d')
    # 提取年份和月份列
    df["年份"] = df["凭证日期"].dt.year
    df["月份"] = df["凭证日期"].dt.month
    # print(df)
    # # 提取领用科室中含有"杭州"的行
    # hangzhou_df = df[df['领用科室'].str.contains('杭州')]
    # # 提取领用科室中含有"宁波"的行
    # ningbo_df = df[df['领用科室'].str.contains('宁波')]
    # # 打印结果
    # print("杭州领用记录：")
    # print(hangzhou_df)
    # print("\n宁波领用记录：")
    # print(ningbo_df)
    # hangzhou_df.to_csv("杭州领用记录.csv", index=False, encoding='utf-8')
    # ningbo_df.to_csv("宁波领用记录.csv", index=False, encoding='utf-8')
    # 使用pivot_table函数将数据透视为所需的格式
    df_pivot = df.pivot_table(index="物料号", columns=["年份", "月份"], values="数量", aggfunc="sum", fill_value=0)
    # # 获取物料号和账册编号的对应关系，筛选帐册编号为[C]的记录，并且只取每个物料号的第一个帐册编号
    # material_to_A = df[df['帐册编号'] == '[A]'][['物料号', '帐册编号']].drop_duplicates(
    #     subset=['物料号']).reset_index(drop=True)
    # material_to_B = df[df['帐册编号'] == '[B]'][['物料号', '帐册编号']].drop_duplicates(
    #     subset=['物料号']).reset_index(drop=True)
    # material_to_C = df[df['帐册编号'] == '[C]'][['物料号', '帐册编号']].drop_duplicates(
    #     subset=['物料号']).reset_index(drop=True)
    #
    #
    # print(material_to_A)
    # print(material_to_B)
    # print(material_to_C)
    # # 将筛选后的数据保存到 CSV 文件中
    # material_to_C.to_csv('帐册C数据_all.csv', index=False, encoding='utf-8')

    # 重置列索引，将年份和月份组合为列名
    df_pivot.columns = [f"{year}.{month:02}" for (year, month) in df_pivot.columns]

    # 将列名转换为DateTime对象
    df_pivot.columns = pd.to_datetime(df_pivot.columns, format="%Y.%m")

    # 按季度对数据进行汇总
    df_quarters = df_pivot.resample("Q", axis=1).sum()
    # 为每个季度列重命名
    quarter_names = ["第1季度", "第2季度", "第3季度", "第4季度"]

    # 获取数据中实际存在的年份，由于列名可能已经是字符串，需要从DataFrame的year列直接获取
    years = sorted(df["年份"].unique())
    # 生成对应的季度名称
    new_column_names = []
    for year in years:
        quarters_in_year = 3 if year == max(years) else 4  # 最后一年的季度数量可能不足四个
        new_column_names.extend([f"{year} {quarter_names[i]}" for i in range(quarters_in_year)])

    df_quarters.columns = new_column_names
    # 在这里先删去2023第三季度，后续在process里就不删了
    # 删除名为 "2023 第3季度" 的列
    df_quarters = df_quarters.drop(columns=["2023 第3季度"])

    # print("zheshi1:",df_quarters.columns)
    non_zero_demand_count = (df_quarters.iloc[:, 0:] != 0).sum(axis=1)
    logger.debug("Non-zero demand count: %s", non_zero_demand_count)
    # print(df_pivot)
    # 计算ADI并添加到最后一列
    # 计算非零需求的总数
    # non_zero_demand_count = (df_pivot.iloc[:, 0:] != 0).sum(axis=1)

    # 计算每年的年度总和
    for year in range(int(df["年份"].min()), df["年份"].max() + 1):
        end_quarter = 2 if year == 2023 else 4

        columns_for_year = [f"{year} 第{quarter}季度" for quarter in range(1, end_quarter + 1)]

        year_sum = df_quarters[columns_for_year].sum(axis=1)
        year_mean = df_quarters[columns_for_year].mean(axis=1)
        year_std = df_quarters[columns_for_year].std(axis=1)
        year_by = year_std / year_mean

        # 在每年末尾插入年度总和列
        try:
            insert_position = df_quarters.columns.get_loc(f"{year} 第{end_quarter}季度")
            if isinstance(insert_position, int):
                insert_position += 1
                df_quarters.insert(insert_position, f"{year}年度总和", year_sum)
                df_quarters.insert(insert_position + 1, f"{year}年均值", year_mean)
                df_quarters.insert(insert_position + 2, f"{year}年标准差", year_std)
                df_quarters.insert(insert_position + 3, f"{year}年变异系数", year_by)
        except KeyError:
            logger.warning("未找到列: %s 第%d季度", year, end_quarter)
    # print(df_pivot)
    exclude_cols = ["年度总和", "年均值", "年标准差", "年变异系数"]
    # filtered_cols = [col for col in df_pivot.columns if all(exclude not in col for exclude in exclude_cols)]
    filtered_cols = [
        str(col) for col in df_quarters.columns if all(exclude not in str(col) for exclude in exclude_cols)
    ]

    all_years_mean = df_quarters[filtered_cols].mean(axis=1)
    # print(all_years_mean)
    all_years_var = df_quarters[filtered_cols].var(axis=1)
    all_years_std = df_quarters[filtered_cols].std(axis=1)
    # 计算所有年份的均值（不包括年度总和列）
    # all_years_mean = df_quarters[[col for col in df_quarters.columns if '年度总和' not in col]].mean(axis=1)
    # all_years_var = df_quarters[[col for col in df_quarters.columns if '年度总和' not in col]].var(axis=1)
    # all_years_std = df_quarters[[col for col in df_quarters.columns if '年度总和' not in col]].std(axis=1)
    df_quarters["所有年均值"] = all_years_mean
    df_quarters["所有方差"] = all_years_var
    df_quarters["所有标准差"] = all_years_std
    df_quarters["所有年变异系数"] = all_years_std / all_years_mean
    df_pivot = df_quarters
    # 计算ADI并添加到最后一列
    # 计算非零需求的总数

    df_pivot["ADI"] = 22 / non_zero_demand_count

    # 重置索引，使物料号成为列
    df_pivot = df_pivot.reset_index()

    # 添加物料描述列
    material_description = df[["物料号", "物料描述"]].drop_duplicates(subset=["物料号"]).set_index("物料号")  # pyright: ignore[reportCallIssue]
    df_pivot = df_pivot.join(material_description, on="物料号")
    # print(len(df_pivot))
    # df_pivot.to_csv("all数据表.csv", index=False, encoding='utf-8')
    # 找出所有年均值为0的物料数量
    zero_mean_count = (df_pivot["所有年均值"] == 0).sum()
    logger.info("所有年均值为0的物料数量：%d", zero_mean_count)

    # 创建"间歇性数据"子数据集
    intermittent_data = df_pivot[
        (df_pivot["ADI"] > 1.32) & (abs(df_pivot["所有年变异系数"]) <= 0.7) & (df_pivot["所有年均值"] < 0)
    ]

    # 创建"块状需求"子数据集
    block_demand_data = df_pivot[
        (df_pivot["ADI"] > 1.32) & (abs(df_pivot["所有年变异系数"]) > 0.7) & (df_pivot["所有年均值"] < 0)
    ]
    # 创建"需求平稳"子数据集
    stable_demand_data = df_pivot[
        (df_pivot["ADI"] <= 1.32) & (abs(df_pivot["所有年变异系数"]) <= 0.7) & (df_pivot["所有年均值"] < 0)
    ]
    # 创建"不稳定需求"子数据集
    unstable_demand_data = df_pivot[
        (df_pivot["ADI"] <= 1.32) & (abs(df_pivot["所有年变异系数"]) > 0.7) & (df_pivot["所有年均值"] < 0)
    ]
    #
    # 打印"间歇性数据"子数据集
    logger.info("间歇性数据 (ADI > 1.32 且 CV² <= 0.49): 数量: %d", len(intermittent_data))
    logger.debug("间歇性数据详情: %s", intermittent_data)

    # 打印"块状需求"子数据集
    logger.info("块状需求 (ADI > 1.32 且 CV² > 0.49): 数量: %d", len(block_demand_data))
    logger.debug("块状需求详情: %s", block_demand_data)
    #
    # 打印"需求平稳"子数据集
    logger.info("需求平稳 (ADI <= 1.32 且 CV² <= 0.49): 数量: %d", len(stable_demand_data))
    logger.debug("需求平稳详情: %s", stable_demand_data)
    stable_demand_data.to_csv("平稳杭宁.csv", index=False, encoding="utf-8")
    # 提取稳定需求数据中的物料号
    # material_numbers_stable = stable_demand_data["物料号"]
    # # 使用 merge 函数，将两个数据框根据物料号进行合并，判断是否在 df_c 中
    # 注意：material_to_C 变量需要在调用此函数前定义
    # merged_df = pd.merge(material_numbers_stable, material_to_C[["物料号"]], on="物料号", how="inner")
    # logger.info("合并后的数据条数: %d", len(merged_df))
    # merged_df.to_csv("都包含帐册C数据.csv", index=False, encoding="utf-8")
    # 提取需求平稳数据集中 ADI 等于 1 的数据
    adi_equals_1_data = stable_demand_data[stable_demand_data["ADI"] == 1]
    # # 打印 ADI 等于 1 的数据
    logger.info("需求平稳且 ADI = 1 的数据: 数量: %d", len(adi_equals_1_data))
    logger.debug("需求平稳且 ADI = 1 的详情: %s", adi_equals_1_data)
    adi_equals_1_data.to_csv("稳定杭宁.csv", index=False, encoding="utf-8")

    # 打印"不稳定需求"子数据集
    logger.info("不稳定需求 (ADI <= 1.32 且 CV² > 0.49): 数量: %d", len(unstable_demand_data))
    logger.debug("不稳定需求详情: %s", unstable_demand_data)
    # unstable_demand_data.to_csv("不平稳杭宁.csv", index=False, encoding='utf-8')
    # 提取需求不平稳数据集中 ADI 等于 1 的数据
    adi_equals_1_data_2 = unstable_demand_data[unstable_demand_data["ADI"] == 1]
    # # 打印 ADI 等于 1 的数据
    logger.info("不稳定需求且 ADI = 1 的数据: 数量: %d", len(adi_equals_1_data_2))
    logger.debug("不稳定需求且 ADI = 1 的详情: %s", adi_equals_1_data_2)
    # adi_equals_1_data_2.to_csv("不稳定杭宁.csv", index=False, encoding='utf-8')

    intermittent_data.to_csv("间歇性需求_季度_all.csv", index=False, encoding="utf-8")
    block_demand_data.to_csv("块状需求_季度_all.csv", index=False, encoding="utf-8")
    unstable_demand_data.to_csv("不稳定需求_季度_all.csv", index=False, encoding="utf-8")
    stable_demand_data.to_csv("需求平稳_季度_杭州.csv", index=False, encoding="utf-8")
    unstable_demand_data.to_csv("不稳定需求_季度_杭州.csv", index=False, encoding="utf-8")
    logger.debug("数据透视表: %s", df_pivot)
    df_pivot.to_csv("季度数据_all.csv", index=False, encoding="utf-8")

    return df_pivot


def preprocess_try(input_file: str = "不稳定杭宁.csv") -> pd.DataFrame:
    """
    预处理数据，将CSV文件转换为适用于预测的格式

    Args:
        input_file: 输入的CSV文件路径

    Returns:
        预处理后的DataFrame
    """
    # 读取CSV文件
    df = pd.read_csv(input_file, encoding="utf-8")

    # df = pd.read_csv("新不稳定需求_季度_ADI=1_hz.csv", encoding="ANSI")
    # df = pd.read_csv("新需求平稳_季度_ADI=1_nb.csv", encoding="ANSI")
    # df = pd.read_csv("新不稳定需求_季度_ADI=1_nb.csv", encoding="ANSI")

    # print(df)
    # 定义一个函数，用于将负数转换为正数
    def make_positive(x: Any) -> Any:
        if isinstance(x, int | float):
            return abs(x)
        return x  # 保持其他类型不变

    # 使用map方法应用函数，只影响数值列
    df = df.map(lambda x: make_positive(x))

    # 获取要删除的列名列表
    # columns_to_delete = [col for col in df.columns if col.endswith(
    #     ('均值', '标准差', '方差', '变异系数', '总和', 'ADI'))]
    columns_to_delete = [
        col for col in df.columns if col.endswith(("均值", "标准差", "方差", "变异系数", "总和", "ADI", "物料描述"))
    ]

    # 使用 drop 方法删除这些列
    df = df.drop(columns=columns_to_delete)

    # 更改日期格式
    df.columns = [col.replace(".", "/") for col in df.columns]

    # 获取列索引
    columns = df.columns

    # 重置列索引为默认整数索引
    df = df.reset_index(drop=True)

    # 创建一个新行，将列索引作为值
    new_row = pd.DataFrame([columns], columns=df.columns)

    # 将新行添加到DataFrame的顶部
    df = pd.concat([new_row, df], axis=0, ignore_index=True)

    # 转置矩阵
    df = df.set_index(df.columns[0]).transpose()

    # 重置行索引为默认整数索引
    df = df.reset_index(drop=True)

    # 删除行索引的列名
    df = df.rename_axis(None, axis=1)

    # 更换'物料号'列索引为'time'
    df = df.rename(columns={"物料号": "time"})

    # # 将'time'列转换为时间格式
    # df['time'] = pd.to_datetime(df['time'], format='%Y/%m')
    # print(df)
    # 删去存在0的列
    # non_zero_columns = df.loc[:, (df != 0).all()]
    # df = non_zero_columns

    # print(df)
    # df.to_csv("宁波厂全部备件季度数据.csv", index=False, encoding='ANSI')
    return df.rename_axis(None, axis=1).rename(columns={"物料号": "time"})
