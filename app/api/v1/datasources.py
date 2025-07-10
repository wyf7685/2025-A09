"""
数据源管理接口
"""

import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.const import UPLOAD_DIR
from app.core.datasource import DataSource, create_csv_source, create_dremio_source
from app.core.datasource.source import DataSourceMetadata
from app.core.dremio import DremioSource
from app.core.dremio.rest import DremioClient
from app.log import logger
from app.utils import run_sync

# 创建路由
router = APIRouter(prefix="/datasources")

# 数据源存储
datasources: dict[str, DataSource] = {}


def register_datasource(source: DataSource) -> str:
    """
    注册数据源

    Args:
        source: 数据源对象

    Returns:
        str: 数据源ID
    """
    source_id = str(uuid.uuid4())
    datasources[source_id] = source
    return source_id


class RegisterDataSourceRequest(BaseModel):
    source: DremioSource


class RegisterDataSourceResponse(BaseModel):
    source_id: str
    metadata: DataSourceMetadata


@router.post("/register", response_model=RegisterDataSourceResponse)
async def register_dremio_source(data: RegisterDataSourceRequest) -> dict[str, Any]:
    """
    注册数据源API

    接收数据源信息，创建DataSource实例并注册
    """
    try:
        # 创建数据源
        source = create_dremio_source(data.source)
        source_id = register_datasource(source)
        return {"source_id": source_id, "metadata": source.metadata}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("注册数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to register datasource: {e}") from e


@router.post("/upload", response_model=RegisterDataSourceResponse)
async def upload_file(
    file: UploadFile = File(...),
    source_name: str | None = Form(None),
) -> dict[str, Any]:
    """
    上传CSV/Excel文件并创建数据源
    """
    try:
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # 保存文件
        file_path = UPLOAD_DIR / file.filename
        file_path.write_bytes(await file.read())

        # 创建CSV数据源
        source = create_csv_source(file_path, name=source_name or file.filename)
        source_id = register_datasource(source)
        return {"source_id": source_id, "metadata": source.metadata}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("上传文件失败")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}") from e


@router.get("")
async def list_datasources() -> list[str]:
    """
    获取数据源列表
    """
    try:
        client = DremioClient()
        for ds in await run_sync(client.list_sources)():
            source_name = ".".join(ds.path)
            if not any(
                source.metadata.name == source_name
                for source in datasources.values()
                if source.metadata.source_type == "dremio"
            ):
                register_datasource(create_dremio_source(ds))
        return list(datasources)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取数据源列表失败")
        raise HTTPException(status_code=500, detail=f"Failed to list datasources: {e}") from e


@router.get("/{source_id}")
async def get_datasource(source_id: str) -> DataSourceMetadata:
    """
    获取数据源详情
    """
    try:
        if source_id not in datasources:
            raise HTTPException(status_code=404, detail="Datasource not found")
        return datasources[source_id].metadata

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取数据源详情失败")
        raise HTTPException(status_code=500, detail=f"Failed to get datasource: {e}") from e


class GetDataSourceDataResponse(BaseModel):
    data: list[dict[str, Any]]
    total: int
    skip: int
    limit: int


@router.get("/{source_id}/data", response_model=GetDataSourceDataResponse)
async def get_datasource_data(
    source_id: str,
    limit: int = 100,
    skip: int = 0,
) -> dict[str, Any]:
    """
    获取数据源数据

    支持分页获取数据
    """
    try:
        if source_id not in datasources:
            raise HTTPException(status_code=404, detail="Datasource not found")

        source = datasources[source_id]

        # 获取数据
        data = source.get_data(limit + skip)
        if skip > 0:
            data = data.iloc[skip:]

        # 获取总行数
        total_rows = source.metadata.row_count
        if total_rows is None:
            # 如果元数据中没有行数信息，可以选择加载完整数据获取行数
            # 但这可能影响性能，所以这里只是返回已加载的数据行数
            total_rows = len(data) + skip

        return {
            "data": data.to_dict(orient="records"),
            "total": total_rows,
            "skip": skip,
            "limit": limit,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取数据源数据失败")
        raise HTTPException(status_code=500, detail=f"Failed to get datasource data: {e}") from e


@router.delete("/{source_id}")
async def delete_datasource(source_id: str) -> dict[str, Any]:
    """
    删除数据源
    """
    if source_id not in datasources:
        raise HTTPException(status_code=404, detail="Datasource not found")

    try:
        # 从数据源字典中删除
        datasources.pop(source_id)

        # 删除关联的会话
        from .sessions import sessions

        for session_id, session in list(sessions.items()):
            if session.dataset_id == source_id:
                del sessions[session_id]

        return {"success": True, "message": f"Datasource {source_id} deleted"}

    except Exception as e:
        logger.exception("删除数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to delete datasource: {e}") from e
