"""
数据源管理接口
"""

import asyncio
import contextlib
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.const import UPLOAD_DIR
from app.core.config import settings
from app.core.datasource import create_dremio_source
from app.core.datasource.source import DataSourceMetadata
from app.core.dremio import get_dremio_client
from app.log import logger
from app.schemas.dremio import AnyDatabaseConnection, DremioDatabaseType
from app.services.datasource import datasource_service
from app.services.session import session_service
from app.utils import run_sync

# 创建路由
router = APIRouter(prefix="/datasources")


class RegisterDataSourceResponse(BaseModel):
    source_id: str
    metadata: DataSourceMetadata


@router.post("/upload", response_model=RegisterDataSourceResponse)
async def upload_file(file: UploadFile = File(), source_name: str | None = Form(None)) -> dict[str, Any]:
    """
    上传CSV/Excel文件并创建数据源
    """
    try:
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in {".csv", ".xlsx", ".xls"}:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # 保存文件
        file_path = UPLOAD_DIR / f"{uuid.uuid4()}{file_ext}"
        file_path.write_bytes(await file.read())

        client = get_dremio_client()
        dremio_source = await run_sync(client.add_data_source_file)(file_path)
        source = create_dremio_source(dremio_source, source_name)
        source_id = datasource_service.register(source)
        return {"source_id": source_id, "metadata": source.metadata}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("上传文件失败")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}") from e


class AddDataSourceDatabaseRequest(BaseModel):
    database_type: DremioDatabaseType
    connection: AnyDatabaseConnection
    name: str | None = None
    description: str | None = None


@router.post("/database")
async def add_data_source_database(request: AddDataSourceDatabaseRequest) -> RegisterDataSourceResponse:
    """
    添加数据库数据源
    """
    try:
        client = get_dremio_client()
        dremio_source = await run_sync(client.add_data_source_database)(request.database_type, request.connection)
        source = create_dremio_source(dremio_source)
        source_id = datasource_service.register(source)
        if request.name:
            source.metadata.name = request.name
        if request.description:
            source.metadata.description = request.description
        datasource_service.save_source(source_id, source)
        return RegisterDataSourceResponse(source_id=source_id, metadata=source.metadata)
    except Exception as e:
        logger.exception("添加数据库数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to add database datasource: {e}") from e


class UpdateDataSourceRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.put("/{source_id}", response_model=DataSourceMetadata)
async def update_datasource(source_id: str, data: UpdateDataSourceRequest) -> DataSourceMetadata:
    """
    更新数据源信息

    支持修改数据源的名称和描述
    """
    try:
        if not datasource_service.source_exists(source_id):
            raise HTTPException(status_code=404, detail="Datasource not found")

        source = datasource_service.get_source(source_id)

        # 更新元数据
        if data.name is not None:
            source.metadata.name = data.name

        if data.description is not None:
            source.metadata.description = data.description

        datasource_service.save_source(source_id, source)
        return source.metadata
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to update datasource: {e}") from e


list_ds_sem = asyncio.Semaphore(1)


@router.get("")
async def list_datasources() -> list[str]:
    """
    获取数据源列表
    """
    try:
        with contextlib.suppress(Exception):
            async with list_ds_sem:
                await run_sync(datasource_service.sync_from_dremio)()
        return list(datasource_service.sources)
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
        if not datasource_service.source_exists(source_id):
            raise HTTPException(status_code=404, detail="Datasource not found")
        return datasource_service.get_source(source_id).metadata

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
        if not datasource_service.source_exists(source_id):
            raise HTTPException(status_code=404, detail="Datasource not found")

        source = datasource_service.get_source(source_id)

        # 获取数据
        data = source.get_data(limit + skip)
        if skip > 0:
            data = data.iloc[skip:]

        # 获取总行数
        rows, _ = source.get_shape()

        return {
            "data": data.to_dict(orient="records"),
            "total": rows,
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
    if not datasource_service.source_exists(source_id):
        raise HTTPException(status_code=404, detail="Datasource not found")

    try:
        source = datasource_service.get_source(source_id)

        # 如果是Dremio数据源，尝试从Dremio中删除
        if source.metadata.source_type.startswith("dremio"):
            try:
                # 这里需要根据实际情况实现Dremio数据源的删除
                # 目前Dremio REST API没有直接删除数据源的接口，但可以根据实际情况处理
                # 例如，如果是上传的文件，可以从external目录中删除
                if (
                    source.metadata.id.startswith("external.")
                    # 从路径中提取文件名
                    and (file_name := source.metadata.id.removeprefix("external."))
                    and (fp := settings.DREMIO_EXTERNAL_DIR / file_name).exists()
                ):
                    # 删除external目录中的文件
                    fp.unlink()
                    logger.info(f"已从Dremio external目录删除文件: {file_name}")
            except Exception as e:
                logger.warning(f"从Dremio中删除数据源失败: {e}")

        # 从数据源字典中删除
        datasource_service.delete_source(source_id)

        # 删除关联的会话
        for session in list(session_service.sessions.values()):
            if session.dataset_id == source_id:
                session_service.delete_session(session.id)

        return {"success": True, "message": f"Datasource {source_id} deleted"}

    except Exception as e:
        logger.exception("删除数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to delete datasource: {e}") from e
