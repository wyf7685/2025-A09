"""
规则挖掘工具模块 - 工具3和工具4
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import numpy as np
from sklearn.cluster import KMeans
from sklearn.tree import DecisionTreeClassifier

if TYPE_CHECKING:
    import pandas as pd


def mine_fault_rules(
    df: pd.DataFrame, target_col: str = "fail", min_confidence: float = 0.7, max_rules: int = 5
) -> dict[str, Any]:
    """
    工具3: 故障规则挖掘

    使用决策树提取可解释的故障规则。

    Args:
        df: 数据框
        target_col: 故障标签列名
        min_confidence: 最小置信度阈值
        max_rules: 最多返回的规则数

    Returns:
        包含挖掘出的规则及其统计信息的字典
    """
    # 获取特征和标签
    feature_cols = [col for col in df.columns if col != target_col]
    X = df[feature_cols]
    y = df[target_col]

    # 训练决策树
    clf = DecisionTreeClassifier(
        max_depth=4,  # 限制深度保证规则简单
        min_samples_leaf=max(5, len(df) // 200),  # 动态调整最小叶子样本数
        min_samples_split=max(10, len(df) // 100),
        random_state=42,
    )
    clf.fit(X, y)

    # 提取规则
    tree = clf.tree_
    feature_names = feature_cols

    def extract_rules(node: int = 0, conditions: list | None = None) -> list[dict[str, Any]]:
        """递归提取规则"""
        if conditions is None:
            conditions = []

        # 如果是叶子节点
        if tree.feature[node] == -2:  # type: ignore
            samples = tree.n_node_samples[node]  # type: ignore
            fault_samples = tree.value[node][0][1]  # type: ignore
            normal_samples = tree.value[node][0][0]  # type: ignore

            if fault_samples > normal_samples and samples > 0:  # 故障样本占多数
                confidence = fault_samples / samples
                support = samples / len(df)

                if confidence >= min_confidence:
                    return [
                        {
                            "conditions": conditions.copy(),
                            "confidence": confidence,
                            "support": support,
                            "fault_samples": int(fault_samples),
                            "total_samples": int(samples),
                        }
                    ]
            return []

        # 递归处理左右子树
        feature = feature_names[tree.feature[node]]  # type: ignore
        threshold = tree.threshold[node]  # type: ignore

        rules = []

        # 左子树 (<=)
        left_conditions = [*conditions, (feature, "<=", threshold)]
        rules.extend(extract_rules(tree.children_left[node], left_conditions))  # type: ignore

        # 右子树 (>)
        right_conditions = [*conditions, (feature, ">", threshold)]
        rules.extend(extract_rules(tree.children_right[node], right_conditions))  # type: ignore

        return rules

    all_rules = extract_rules()

    # 按置信度和支持度排序
    all_rules.sort(key=lambda x: (x["confidence"], x["support"]), reverse=True)

    # 限制规则数量
    top_rules = all_rules[:max_rules]

    # 格式化规则
    formatted_rules = []
    total_coverage = 0

    for rule in top_rules:
        # 构建规则文本
        rule_parts = []
        for feature, op, threshold in rule["conditions"]:
            if op == "<=":
                rule_parts.append(f"{feature} <= {threshold:.1f}")
            else:
                rule_parts.append(f"{feature} > {threshold:.1f}")

        rule_text = "IF " + " AND ".join(rule_parts) + " THEN 故障"

        coverage_pct = (rule["fault_samples"] / df[target_col].sum()) * 100
        total_coverage += coverage_pct

        formatted_rules.append(
            {
                "rule": rule_text,
                "confidence": round(rule["confidence"], 3),
                "support": round(rule["support"], 3),
                "fault_samples_covered": rule["fault_samples"],
                "coverage": f"覆盖了{rule['fault_samples']}个故障样本 ({coverage_pct:.1f}%)",
            }
        )

    # 统计信息
    total_faults = int(df[target_col].sum())

    return {
        "total_fault_samples": total_faults,
        "rules_found": len(formatted_rules),
        "rules": formatted_rules,
        "total_coverage": f"这些规则共覆盖了{total_coverage:.1f}%的故障案例",
        "min_confidence_threshold": min_confidence,
    }


def analyze_fault_patterns(df: pd.DataFrame, target_col: str = "fail", n_clusters: int = 3) -> dict[str, Any]:
    """
    工具4: 故障模式聚类分析

    将故障样本聚类，识别不同类型的故障模式。

    Args:
        df: 数据框
        target_col: 故障标签列名
        n_clusters: 聚类数量

    Returns:
        包含故障模式分析结果的字典
    """
    # 提取故障样本
    fault_samples = df[df[target_col] == "True"]

    if len(fault_samples) < n_clusters:
        return {"error": f"故障样本数量({len(fault_samples)})少于聚类数({n_clusters})", "fault_patterns": []}

    # 获取特征列
    feature_cols: list[str] = [col for col in df.columns if col != target_col]
    X_fault = fault_samples[feature_cols]

    # 正常样本的均值（用于对比）
    normal_samples = df[df[target_col] == "False"]
    normal_means = cast("pd.Series", normal_samples[feature_cols].mean())

    # K-means聚类
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)  # pyright: ignore[reportArgumentType]
    fault_samples_copy = fault_samples.copy()
    fault_samples_copy["cluster"] = kmeans.fit_predict(X_fault)

    # 分析每个聚类
    patterns = []

    for cluster_id in range(n_clusters):
        cluster_data = cast("pd.DataFrame", fault_samples_copy[fault_samples_copy["cluster"] == cluster_id])
        cluster_size = len(cluster_data)
        cluster_pct = (cluster_size / len(fault_samples)) * 100

        # 计算聚类中心的特征均值
        cluster_means = cast("pd.Series", cluster_data[feature_cols].mean())

        # 识别显著特征（与正常样本差异大的）
        significant_features = []
        for col in feature_cols:
            cluster_val = float(cluster_means[col])
            normal_val = float(normal_means[col])

            if normal_val != 0:
                diff_pct = ((cluster_val - normal_val) / abs(normal_val)) * 100

                if abs(diff_pct) > 20:  # 差异超过20%
                    status = "高" if diff_pct > 0 else "低"
                    significant_features.append(
                        {
                            "feature": col,
                            "value": round(cluster_val, 2),
                            "normal_value": round(normal_val, 2),
                            "status": status,
                            "diff_pct": abs(diff_pct),
                        }
                    )

        # 按差异排序
        significant_features.sort(key=lambda x: x["diff_pct"], reverse=True)

        # 生成模式名称
        if significant_features:
            top_features = significant_features[:2]
            name_parts = [f"{f['feature']}{f['status']}" for f in top_features]
            pattern_name = "+".join(name_parts) + "型故障"
        else:
            pattern_name = f"模式{cluster_id + 1}型故障"

        # 生成特征描述
        characteristics = {}
        for feat in significant_features[:4]:  # 只显示前4个
            characteristics[feat["feature"]] = (
                f"平均{feat['value']}（{feat['status']}，"
                f"{'高于' if feat['status'] == '高' else '低于'}正常{feat['diff_pct']:.0f}%）"
            )

        # 评估严重程度（基于偏离程度）
        if significant_features:
            avg_deviation = np.mean([f["diff_pct"] for f in significant_features[:3]])
            if avg_deviation > 50:
                severity = "高"
            elif avg_deviation > 30:
                severity = "中"
            else:
                severity = "低"
        else:
            severity = "中"

        patterns.append(
            {
                "pattern_id": cluster_id + 1,
                "name": pattern_name,
                "count": cluster_size,
                "percentage": f"{cluster_pct:.1f}%",
                "characteristics": characteristics,
                "severity": severity,
                "top_features": [f"{f['feature']}({f['status']})" for f in significant_features[:3]],
            }
        )

    # 按数量排序
    patterns.sort(key=lambda x: x["count"], reverse=True)

    # 生成洞察
    insights = []
    for pattern in patterns:
        insights.append(  # noqa: PERF401
            f"{pattern['percentage']}的故障属于{pattern['name']}，主要特征是{', '.join(pattern['top_features'])}"
        )

    return {
        "total_failures": len(fault_samples),
        "n_patterns": n_clusters,
        "fault_patterns": patterns,
        "insights": insights,
    }
