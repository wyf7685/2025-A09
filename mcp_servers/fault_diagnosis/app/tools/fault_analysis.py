"""
故障分析工具模块 - 工具1和工具2
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.spatial.distance import mahalanobis
from scipy.stats import ttest_ind

if TYPE_CHECKING:
    import pandas as pd


def fault_vs_normal_analysis(df: pd.DataFrame, target_col: str = "fail") -> dict[str, Any]:
    """
    工具1: 故障与正常样本对比分析

    对比正常样本和故障样本的特征差异，识别最显著的故障指示特征。

    Args:
        df: 包含故障标签的数据框
        target_col: 故障标签列名，默认为"fail"

    Returns:
        包含对比分析结果的字典
    """
    # 分离正常和故障样本
    normal_samples = df[df[target_col] == 0]
    fault_samples = df[df[target_col] == 1]

    # 获取特征列（排除目标列）
    feature_cols = [col for col in df.columns if col != target_col]

    # 计算故障率
    fault_rate = len(fault_samples) / len(df)

    # 对比每个特征
    comparisons = []
    for col in feature_cols:
        try:
            normal_mean = normal_samples[col].mean()
            fault_mean = fault_samples[col].mean()

            # 计算差异百分比
            diff_pct = float((fault_mean - normal_mean) / abs(normal_mean) * 100) if normal_mean != 0 else 0.0

            # 计算t检验p值
            test_result = ttest_ind(normal_samples[col].dropna(), fault_samples[col].dropna())
            # 获取p值（不同scipy版本返回格式不同）
            try:
                p_value = float(test_result.pvalue)  # type: ignore
            except (AttributeError, TypeError):
                p_value = float(test_result[1])  # type: ignore

            comparisons.append(
                {
                    "feature": col,
                    "normal_mean": round(float(normal_mean), 2),
                    "fault_mean": round(float(fault_mean), 2),
                    "difference": round(float(fault_mean - normal_mean), 2),
                    "diff_percentage": round(float(diff_pct), 1),
                    "p_value": round(p_value, 4),
                    "significant": bool(p_value < 0.05),
                }
            )
        except Exception:  # noqa: S112
            # 跳过无法处理的列
            continue

    # 按差异绝对值排序
    comparisons.sort(key=lambda x: abs(x["diff_percentage"]), reverse=True)

    # 提取Top3最显著的特征
    top_discriminators = comparisons[:3]

    # 生成解释文本
    interpretation_parts = []
    for item in top_discriminators:
        direction = "偏高" if item["diff_percentage"] > 0 else "偏低"
        interpretation_parts.append(f"{item['feature']}{direction}{abs(item['diff_percentage']):.0f}%")

    interpretation = "、".join(interpretation_parts) + " 是故障的主要特征"

    return {
        "fault_rate": round(fault_rate, 3),
        "total_samples": len(df),
        "normal_samples": len(normal_samples),
        "fault_samples": len(fault_samples),
        "top_discriminators": top_discriminators,
        "all_comparisons": comparisons,
        "interpretation": interpretation,
    }


def calculate_health_score(
    df: pd.DataFrame,
    sample_index: int | None = None,
    target_col: str = "fail",
) -> dict[str, Any]:
    """
    工具2: 健康度评分

    基于马氏距离计算样本偏离正常状态的程度，输出健康度评分和异常传感器。

    Args:
        df: 数据框
        sample_index: 要评估的样本索引，None表示最新样本（最后一行）
        target_col: 故障标签列名

    Returns:
        包含健康度评分和诊断信息的字典
    """
    # 获取特征列
    feature_cols = [col for col in df.columns if col != target_col]

    # 提取正常样本作为基线
    normal_samples = df[df[target_col] == 0][feature_cols]

    if len(normal_samples) < 2:
        return {"error": "正常样本数量不足，无法计算健康度", "health_score": None}

    # 计算正常样本的均值和协方差矩阵
    normal_mean = normal_samples.mean()
    normal_cov = normal_samples.cov()

    # 处理奇异协方差矩阵
    try:
        normal_cov_inv = np.linalg.inv(normal_cov)
    except np.linalg.LinAlgError:
        # 使用伪逆
        normal_cov_inv = np.linalg.pinv(normal_cov)

    # 选择要评估的样本
    if sample_index is None:
        sample_index = len(df) - 1

    sample = df.iloc[sample_index][feature_cols]
    actual_fail = df.iloc[sample_index][target_col]

    # 计算马氏距离
    try:
        mahal_dist = mahalanobis(sample, normal_mean, normal_cov_inv)
    except Exception:
        # 如果失败，使用欧氏距离的标准化版本
        mahal_dist = np.sqrt(np.sum(((sample - normal_mean) / normal_samples.std()) ** 2))

    # 将马氏距离转换为健康度评分 (0-100)
    # 距离越大，健康度越低
    health_score = float(max(0.0, min(100.0, 100.0 - float(mahal_dist) * 10)))

    # 确定风险等级
    if health_score >= 80:
        risk_level = "低风险"
    elif health_score >= 60:
        risk_level = "中等风险"
    else:
        risk_level = "高风险"

    # 识别异常的传感器
    abnormal_sensors = []
    for col in feature_cols:
        sample_val = sample[col]
        normal_mean_val = normal_mean[col]
        normal_std_val = normal_samples[col].std()

        if normal_std_val > 0:
            z_score = (sample_val - normal_mean_val) / normal_std_val

            if abs(z_score) > 1.5:  # 偏离超过1.5个标准差
                direction = "偏高" if z_score > 0 else "偏低"
                deviation_pct = abs((sample_val - normal_mean_val) / normal_mean_val * 100)
                abnormal_sensors.append(f"{col}: {direction}{deviation_pct:.0f}%")

    # 生成建议
    if health_score >= 80:
        recommendation = "设备运行正常，继续监控"
    elif health_score >= 60:
        if abnormal_sensors:
            recommendation = f"建议监控 {', '.join([s.split(':')[0] for s in abnormal_sensors[:2]])}，考虑预防性检查"
        else:
            recommendation = "建议进行全面检查"
    else:
        recommendation = "高故障风险！建议立即停机检修"

    return {
        "sample_index": sample_index,
        "health_score": round(health_score, 1),
        "risk_level": risk_level,
        "mahalanobis_distance": round(mahal_dist, 2),
        "abnormal_sensors": abnormal_sensors,
        "total_abnormal_count": len(abnormal_sensors),
        "actual_failure": bool(actual_fail),
        "recommendation": recommendation,
        "sample_values": {col: round(sample[col], 2) for col in feature_cols},
    }
