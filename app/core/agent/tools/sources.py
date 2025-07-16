from langchain_core.tools import BaseTool, tool

from app.core.agent.schemas import Sources


def sources_tools(sources: Sources) -> list[BaseTool]:
    @tool
    def list_dataset_tool() -> str:
        """
        列出当前可用的所有数据集及其概览信息。

        此工具用于查看当前环境中所有可用数据集的信息，包括每个数据集的：
        - 数据集ID（用于在其他工具中引用该数据集）
        - 行数和列数
        - 列名和数据类型
        - 数据集描述（如果有）

        当你需要了解当前可用的数据集或查询某个数据集的基本信息时，
        应该首先使用此工具。

        Returns:
            str: 格式化的数据集信息列表，每个数据集包含ID和概览
        """
        return "\n\n".join(
            f"数据集ID: {source_id}\n{source.format_overview()}" for source_id, source in sources.items()
        )

    @tool
    def rename_dataset_tool(dataset_id: str, new_dataset_id: str) -> str:
        """
        重命名指定的数据集。

        此工具用于更改数据集的ID，使其更符合当前分析任务的语义。
        重命名后，在所有其他工具中需要使用新的数据集ID来引用该数据集。

        Args:
            dataset_id (str): 当前的数据集ID
            new_dataset_id (str): 新的数据集ID

        Returns:
            str: 操作成功的确认消息

        Raises:
            ValueError: 如果指定的原始数据集ID不存在
        """
        if dataset_id not in sources:
            raise ValueError(f"数据集 {dataset_id} 不存在")
        sources[new_dataset_id] = sources.pop(dataset_id)
        return f"数据集 {dataset_id} 已重命名为 {new_dataset_id}"

    return [
        list_dataset_tool,
        rename_dataset_tool,
    ]
