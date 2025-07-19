from pathlib import Path

import pandas as pd

from app.log import logger

from .schemas import CleaningState


def load_data(state: CleaningState) -> CleaningState:
    """加载数据文件"""
    try:
        file_path = Path(state["file_path"])
        logger.info(f"加载数据文件: {file_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 根据文件扩展名读取数据
        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

        if df.empty:
            raise ValueError("数据文件为空")

        state["df_data"] = df.to_dict()  # 序列化DataFrame
        logger.info(f"成功加载数据: {len(df)} 行, {len(df.columns)} 列")
        return state

    except Exception as e:
        logger.error(f"加载数据失败: {e}")
        state["error_message"] = str(e)
        return state
