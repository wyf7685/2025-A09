from app.core.datasource import create_file_source
from app.log import logger
from app.services.datasource import temp_source_service

from .schemas import CleaningState


def load_data(state: CleaningState) -> CleaningState:
    """加载数据文件"""
    try:
        file_path = state["file_path"]
        logger.info(f"加载数据文件: {file_path}")

        source = create_file_source(file_path)
        df = source.get_full()

        if df.empty:
            raise ValueError("数据文件为空")

        state["source_id"] = temp_source_service.register(source)
        logger.info(f"成功加载数据: {len(df)} 行, {len(df.columns)} 列")
        return state

    except Exception as e:
        logger.error(f"加载数据失败: {e}")
        state["error_message"] = str(e)
        return state
