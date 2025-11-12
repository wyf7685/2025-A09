# ruff: noqa: T201, F541
from pathlib import Path

import pandas as pd

from app.tools import analyze_fault_patterns, calculate_health_score, fault_vs_normal_analysis


def test_tool_1(df: pd.DataFrame) -> None:
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


def test_tool_2(df: pd.DataFrame) -> None:
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


def test_tool_4(df: pd.DataFrame) -> None:
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


def test_with_sample_data() -> None:
    """使用示例数据测试所有工具"""

    # 加载数据
    data_path = Path(__file__).parent / "test.csv"

    if not data_path.exists():
        print(f"错误: 找不到数据文件 {data_path}")
        return

    print(f"加载数据: {data_path}")
    df = pd.read_csv(data_path)
    print(f"数据形状: {df.shape}")
    print(f"故障率: {df['fail'].mean():.2%}\n")

    test_tool_1(df)
    test_tool_2(df)
    test_tool_4(df)

    print("\n" + "=" * 80)
    print("所有工具测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_with_sample_data()
