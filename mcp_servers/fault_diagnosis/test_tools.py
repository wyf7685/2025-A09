"""
测试故障诊断MCP工具
"""

# ruff: noqa T201
import pandas as pd
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from app.tools import (
    fault_vs_normal_analysis,
    calculate_health_score,
    mine_fault_rules,
    analyze_fault_patterns,
)


def test_with_sample_data():
    """使用示例数据测试所有工具"""

    # 加载数据
    data_path = Path(__file__).parent.parent.parent / "local" / "data.csv"

    if not data_path.exists():
        print(f"错误: 找不到数据文件 {data_path}")
        return

    print(f"加载数据: {data_path}")
    df = pd.read_csv(data_path)
    print(f"数据形状: {df.shape}")
    print(f"故障率: {df['fail'].mean():.2%}\n")

    print("=" * 80)
    print("工具1: 故障特征对比分析")
    print("=" * 80)
    result1 = fault_vs_normal_analysis(df)
    print(f"故障率: {result1['fault_rate']:.3f}")
    print(f"正常样本: {result1['normal_samples']}, 故障样本: {result1['fault_samples']}")
    print(f"\nTop3 显著特征:")
    for item in result1["top_discriminators"]:
        print(
            f"  {item['feature']}: 正常={item['normal_mean']}, 故障={item['fault_mean']}, "
            f"差异={item['diff_percentage']:+.1f}% (p={item['p_value']:.4f})"
        )
    print(f"\n解释: {result1['interpretation']}\n")

    print("=" * 80)
    print("工具2: 健康度评分")
    print("=" * 80)
    result2 = calculate_health_score(df, sample_index=-1)
    print(f"样本索引: {result2['sample_index']}")
    print(f"健康度评分: {result2['health_score']}")
    print(f"风险等级: {result2['risk_level']}")
    print(f"马氏距离: {result2['mahalanobis_distance']}")
    print(f"异常传感器数量: {result2['total_abnormal_count']}")
    if result2["abnormal_sensors"]:
        print("异常传感器:")
        for sensor in result2["abnormal_sensors"]:
            print(f"  - {sensor}")
    print(f"实际故障: {result2['actual_failure']}")
    print(f"建议: {result2['recommendation']}\n")

    print("=" * 80)
    print("工具3: 故障规则挖掘")
    print("=" * 80)
    result3 = mine_fault_rules(df, min_confidence=0.7)
    print(f"总故障样本: {result3['total_fault_samples']}")
    print(f"挖掘到的规则数: {result3['rules_found']}")
    print(f"\n规则列表:")
    for i, rule in enumerate(result3["rules"], 1):
        print(f"\n规则{i}:")
        print(f"  {rule['rule']}")
        print(f"  置信度: {rule['confidence']:.3f}, 支持度: {rule['support']:.3f}")
        print(f"  {rule['coverage']}")
    print(f"\n{result3['total_coverage']}\n")

    print("=" * 80)
    print("工具4: 故障模式聚类")
    print("=" * 80)
    result4 = analyze_fault_patterns(df, n_clusters=3)
    print(f"总故障数: {result4['total_failures']}")
    print(f"识别的故障模式数: {result4['n_patterns']}\n")
    for pattern in result4["fault_patterns"]:
        print(f"\n【{pattern['name']}】")
        print(f"  数量: {pattern['count']} ({pattern['percentage']})")
        print(f"  严重程度: {pattern['severity']}")
        print(f"  主要特征: {', '.join(pattern['top_features'])}")
        if pattern["characteristics"]:
            print(f"  详细特征:")
            for feat, desc in list(pattern["characteristics"].items())[:3]:
                print(f"    - {feat}: {desc}")

    print(f"\n洞察总结:")
    for insight in result4["insights"]:
        print(f"  • {insight}")

    print("\n" + "=" * 80)
    print("所有工具测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_with_sample_data()
