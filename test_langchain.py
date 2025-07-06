# ruff: noqa: T201

import datetime
from pathlib import Path

import dotenv

from app.chain import GeneralDataAnalysis, get_llm
from app.chain.general_analysis import GeneralDataAnalysisInput

dotenv.load_dotenv()


def test_general_analyze() -> None:
    from app.dremio_client import DremioClient

    with DremioClient().data_source_csv(Path("test.csv")) as source:
        df = source.read(fetch_all=True)

    # print("数据预览:")
    # print(df.head().to_string())
    print("\n数据规模:", df.shape)
    print("\n请输入您关注的分析方向（多个方向用逗号分隔，直接回车则不设置侧重点）：")
    print("例如：趋势分析,异常值检测,相关性分析")
    user_input = input("> ").strip()
    focus_areas = [i.strip() for i in user_input.split(",")] if user_input else None

    llm = get_llm().with_retry()
    analyzer = GeneralDataAnalysis(llm)
    report, figures = analyzer.invoke(GeneralDataAnalysisInput(df, focus_areas))
    print("\n\n分析报告:")
    print(report)

    output_dir = Path("output") / datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    for i, figure_data in enumerate(figures):
        with (output_dir / f"figure_{i}.png").open("wb") as f:
            f.write(figure_data)
    print(f"\n\n报告和图表已保存到: {output_dir}")


if __name__ == "__main__":
    test_general_analyze()
