import io
from typing import Annotated

import anyio.to_thread
import pandas as pd
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.agent import DataAnalyzerAgent
from app.core.agent.schemas import DatasetID
from app.log import logger
from app.schemas.session import SessionID
from app.services.agent import daa_service
from app.services.datasource import temp_file_service
from app.services.session import session_service
from app.utils import escape_tag

router = APIRouter(prefix="/agent_source", tags=["AgentSource"])


async def _session_id_from_token(authorization: str = Header(description="Agent数据源令牌")) -> SessionID:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证头")

    token = authorization[len("Bearer ") :]
    session_id = daa_service.get_session_id_by_source_token(token)
    if session_id is None:
        raise HTTPException(status_code=401, detail="无效的Agent数据源令牌")

    return session_id


QuerySessionID = Annotated[SessionID, Depends(_session_id_from_token)]


async def borrow_agent(session_id: QuerySessionID) -> DataAnalyzerAgent:
    session = await session_service.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")

    agent = daa_service.get(session)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 的 Agent 不存在")

    return agent


BorrowedAgent = Annotated[DataAnalyzerAgent, Depends(borrow_agent)]


class DataSourceInfo(BaseModel):
    """数据源信息响应模型"""

    id: str
    name: str
    source_type: str
    description: str
    row_count: int | None
    column_count: int | None
    columns: list[str] | None
    dtypes: dict[str, str] | None


class DataSourceListResponse(BaseModel):
    """数据源列表响应模型"""

    sources: list[DataSourceInfo]
    total: int


class CreateDataSourceResponse(BaseModel):
    """创建数据源响应模型"""

    dataset_id: str
    message: str


@router.get("/list", response_model=DataSourceListResponse)
async def list_sources(session_id: QuerySessionID, agent: BorrowedAgent) -> DataSourceListResponse:
    """列出指定会话Agent中的所有可用数据源"""
    try:
        sources_info = []
        for source_id, source in agent.ctx.sources.items():
            sources_info.append(
                DataSourceInfo(
                    id=source_id,
                    name=source.metadata.name,
                    source_type=source.metadata.source_type,
                    description=source.metadata.description,
                    row_count=source.metadata.row_count,
                    column_count=source.metadata.column_count,
                    columns=source.metadata.columns,
                    dtypes=source.metadata.dtypes,
                )
            )

        logger.opt(colors=True).info(
            f"列出会话 <c>{escape_tag(session_id)}</> 的数据源，共 <y>{len(sources_info)}</> 个"
        )
        return DataSourceListResponse(sources=sources_info, total=len(sources_info))

    except Exception as e:
        logger.opt(colors=True).error(f"获取会话 <c>{escape_tag(session_id)}</> 数据源列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据源列表失败: {e}") from e


@router.get("/info/{source_id}", response_model=DataSourceInfo)
async def get_source_info(source_id: DatasetID, agent: BorrowedAgent) -> DataSourceInfo:
    """获取指定数据源的详细信息"""
    try:
        if not agent.ctx.sources.exists(source_id):
            raise HTTPException(status_code=404, detail=f"数据源 {source_id} 不存在")

        source = agent.ctx.sources.get(source_id)
        logger.opt(colors=True).info(f"获取数据源信息: <c>{escape_tag(source_id)}</>")

        return DataSourceInfo(
            id=source_id,
            name=source.metadata.name,
            source_type=source.metadata.source_type,
            description=source.metadata.description,
            row_count=source.metadata.row_count,
            column_count=source.metadata.column_count,
            columns=source.metadata.columns,
            dtypes=source.metadata.dtypes,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.opt(colors=True).error(f"获取数据源 <c>{escape_tag(source_id)}</> 信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据源信息失败: {e}") from e


@router.get("/data/{source_id}", response_class=FileResponse)
async def read_source_data(source_id: DatasetID, agent: BorrowedAgent) -> FileResponse:
    """读取指定数据源的数据"""
    try:
        if not agent.ctx.sources.exists(source_id):
            raise HTTPException(status_code=404, detail=f"数据源 {source_id} 不存在")

        source = agent.ctx.sources.get(source_id)

        # 读取数据
        data = await source.dump_async()
        _, path = await temp_file_service.allocate(".pkl", 60 * 10)
        await anyio.Path(path).write_bytes(data)

        logger.opt(colors=True).info(f"读取数据源 <c>{escape_tag(source_id)}</> 数据")

        return FileResponse(path, filename=f"{source_id}.pkl")

    except HTTPException:
        raise
    except Exception as e:
        logger.opt(colors=True).error(f"读取数据源 <c>{escape_tag(source_id)}</> 数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取数据源数据失败: {e}") from e


@router.post("/create", response_model=CreateDataSourceResponse)
async def create_source(
    session_id: QuerySessionID,
    agent: BorrowedAgent,
    new_id: str | None = None,
    description: str | None = None,
    file: UploadFile = File(),
) -> CreateDataSourceResponse:
    """在指定会话的Agent中创建新的数据源"""
    try:
        # 读取上传的pickle文件内容
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="数据不能为空")

        # 反序列化pickle数据为DataFrame
        df = await anyio.to_thread.run_sync(pd.read_pickle, io.BytesIO(content))
        if not isinstance(df, pd.DataFrame):
            raise HTTPException(status_code=400, detail="上传的数据必须是DataFrame")

        # 创建数据源
        dataset_id = agent.ctx.sources.create(
            df=df,
            new_id=new_id,
            description=description,
        )

        logger.opt(colors=True).info(
            f"在会话 <c>{escape_tag(session_id)}</> 中创建数据源 <c>{escape_tag(dataset_id)}</>"
        )

        return CreateDataSourceResponse(dataset_id=dataset_id, message=f"成功创建数据源 {dataset_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.opt(colors=True).error(f"在会话 <c>{escape_tag(session_id)}</> 中创建数据源失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建数据源失败: {e}") from e
