import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def generate_test_data(
    output_file: str,
    num_rows: int,
    seed: int | None = None,
) -> pd.DataFrame:
    """
    生成一组完整的学生成绩与信息测试数据

    参数:
        output_file: 输出CSV文件路径
        num_rows: 要生成的行数
        seed: 随机种子，用于复现结果
    """
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    # 创建一个新的DataFrame
    df = pd.DataFrame()

    # 生成学生ID
    df["id"] = range(1, num_rows + 1)

    # 定义科目列表
    subject_names = [
        "math",
        "chinese",
        "english",
        "physics",
        "chemistry",
        "biology",
        "history",
        "geography",
    ]

    # 随机生成各科目的平均分和标准差
    subjects = {}
    for subject in subject_names:
        # 平均分在60-90之间随机
        mean = np.random.uniform(60, 90)
        # 标准差在5-15之间随机
        std = np.random.uniform(5, 15)
        subjects[subject] = (mean, std)

    # 输出生成的科目难度信息
    print("\n生成的科目难度信息:")
    for subject, (mean, std) in subjects.items():
        print(f"{subject}: 平均分={mean:.2f}, 标准差={std:.2f}")

    # 生成各科成绩
    for subject, (mean, std) in subjects.items():
        scores = np.random.normal(mean, std, num_rows)
        # 限制分数在0-100之间
        df[subject] = np.clip(scores.round(), 0, 100).astype(int)

    # 添加学生基本信息
    # 生成随机性别
    df["gender"] = np.random.choice(["男", "女"], size=num_rows)
    # 生成随机年龄(16-20岁)，并与入学年级关联
    df["age"] = np.random.randint(16, 21, num_rows)
    # 生成年级(1-3年级)
    df["grade"] = np.random.randint(1, 4, num_rows)
    # 生成班级(1-10班)
    df["class"] = np.random.randint(1, 11, num_rows)
    # 添加学生所在地区
    regions = ["东部", "西部", "南部", "北部", "中部"]
    region_weights = [0.3, 0.15, 0.2, 0.15, 0.2]  # 不同地区的学生比例
    df["region"] = np.random.choice(regions, size=num_rows, p=region_weights)
    # 添加城乡属性
    urban_rural = ["城市", "城镇", "农村"]
    urban_rural_weights = [0.45, 0.25, 0.3]
    df["residence_type"] = np.random.choice(
        urban_rural, size=num_rows, p=urban_rural_weights
    )

    # 添加新字段: 时间信息
    # 生成入学年份(最近3年)
    current_year = datetime.now().year
    enrollment_years = list(range(current_year - 3, current_year + 1))
    df["enrollment_year"] = np.random.choice(enrollment_years, size=num_rows)
    # 生成随机考试日期(最近6个月内)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    exam_days = pd.date_range(start=start_date, end=end_date, freq="D")
    df["exam_date"] = np.random.choice(exam_days, size=num_rows)
    # 添加期中/期末考试属性
    df["exam_type"] = np.random.choice(["期中考试", "期末考试"], size=num_rows)

    # 添加新字段: 家庭背景
    # 生成随机家庭收入(以万元/年为单位)，根据地区有所差异
    base_income = {"东部": 20, "西部": 12, "南部": 15, "北部": 14, "中部": 16}
    df["family_income"] = (
        df["region"].apply(lambda r: np.random.normal(base_income[r], 5)).round(2)
    )
    df["family_income"] = np.clip(df["family_income"], 5, 50)  # 限制在合理范围
    # 生成随机父母教育水平
    education_levels = ["初中及以下", "高中", "大专", "本科", "硕士及以上"]
    weights = [0.15, 0.25, 0.3, 0.2, 0.1]  # 加权概率
    df["father_education"] = np.random.choice(
        education_levels, size=num_rows, p=weights
    )
    df["mother_education"] = np.random.choice(
        education_levels, size=num_rows, p=weights
    )
    # 添加家庭结构
    family_structures = ["双亲家庭", "单亲家庭", "与祖父母同住", "其他"]
    family_weights = [0.75, 0.12, 0.1, 0.03]
    df["family_structure"] = np.random.choice(
        family_structures, size=num_rows, p=family_weights
    )

    # 添加新字段: 学习习惯和参与度
    # 生成随机每日学习时间(小时)
    df["daily_study_hours"] = np.random.normal(2.5, 1.2, num_rows).round(1)
    df["daily_study_hours"] = np.clip(df["daily_study_hours"], 0.5, 8)
    # 生成课外活动参与度(1-5分)
    df["extracurricular_activity"] = np.random.randint(1, 6, num_rows)
    # 添加课外辅导信息
    df["has_tutor"] = np.random.choice([True, False], size=num_rows, p=[0.4, 0.6])
    # 添加出勤率(百分比)
    df["attendance_rate"] = np.random.normal(92, 8, num_rows).round(1)
    df["attendance_rate"] = np.clip(df["attendance_rate"], 50, 100)
    # 添加睡眠时间
    df["sleep_hours"] = np.random.normal(7, 1, num_rows).round(1)
    df["sleep_hours"] = np.clip(df["sleep_hours"], 4, 10)
    # 添加心理健康状况(1-5分，5分最好)
    df["mental_health"] = np.random.randint(1, 6, num_rows)

    # 生成综合评分(加权平均)
    # 使用动态生成的权重，使难度高的科目权重略低
    total_mean = sum(mean for mean, _ in subjects.values())
    academic_weights = {}
    for subject, (mean, _) in subjects.items():
        # 难度越高(平均分越低)，权重越小
        academic_weights[subject] = (mean / total_mean) * 0.8
    # 归一化权重使总和为0.8
    weight_sum = sum(academic_weights.values())
    for subject in academic_weights:
        academic_weights[subject] = academic_weights[subject] * 0.8 / weight_sum
    # 计算加权学术成绩
    academic_score = 0
    for subject, weight in academic_weights.items():
        academic_score += df[subject] * weight
    # 综合评分考虑学术成绩(80%)和其他因素(20%)
    other_factors = (
        df["attendance_rate"] * 0.1
        + df["mental_health"] * 10 * 0.05
        + df["extracurricular_activity"] * 5 * 0.05
    )
    df["overall_score"] = (academic_score + other_factors).round(2)
    # 添加学习进步指标(相比上次考试)
    df["improvement"] = np.random.normal(0, 5, num_rows).round(2)

    # 保存到CSV
    df.to_csv(output_file, index=False)
    print(f"已生成学生测试数据: {df.shape[0]}行 × {df.shape[1]}列")
    print(f"数据已保存至: {Path(output_file).absolute()}")

    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="生成学生测试数据")
    parser.add_argument("--output", default="test.csv", help="输出CSV文件路径")
    parser.add_argument("--rows", type=int, default=200, help="要生成的学生数量")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，用于复现结果")

    args = parser.parse_args()

    print("开始生成测试数据...")
    generate_test_data(args.output, args.rows, args.seed)
