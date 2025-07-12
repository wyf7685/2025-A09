"""
数据源管理接口
"""

import contextlib
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.const import UPLOAD_DIR
from app.core.datasource import DataSource, create_dremio_source
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

        if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
            raise HTTPException(status_code=400, detail="Unsupported file format")

        # 保存文件
        file_path = UPLOAD_DIR / file.filename
        file_path.write_bytes(await file.read())

        client = DremioClient()
        meth = client.add_data_source_csv if file.filename.lower().endswith(".csv") else client.add_data_source_excel
        source = create_dremio_source(await run_sync(meth)(file_path), source_name)
        source_id = register_datasource(source)
        return {"source_id": source_id, "metadata": source.metadata}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("上传文件失败")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}") from e


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
        if source_id not in datasources:
            raise HTTPException(status_code=404, detail="Datasource not found")
        
        source = datasources[source_id]
        
        # 更新元数据
        if data.name is not None:
            source.metadata.name = data.name
        
        if data.description is not None:
            source.metadata.description = data.description
        
        return source.metadata
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to update datasource: {e}") from e


@router.get("")
async def list_datasources() -> list[str]:
    """
    获取数据源列表
    """
    try:
        with contextlib.suppress(Exception):
            for ds in await run_sync(DremioClient().list_sources)():
                source_name = ".".join(ds.path)
                if not any(
                    source.metadata.name == source_name
                    for source in datasources.values()
                    if source.metadata.source_type.startswith("dremio")
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
        source = datasources[source_id]
        
        # 如果是Dremio数据源，尝试从Dremio中删除
        if source.metadata.source_type.startswith("dremio"):
            try:
                # 这里需要根据实际情况实现Dremio数据源的删除
                # 目前Dremio REST API没有直接删除数据源的接口，但可以根据实际情况处理
                # 例如，如果是上传的文件，可以从external目录中删除
                if hasattr(source.metadata, "id") and source.metadata.id.startswith("external."):
                    # 从路径中提取文件名
                    file_name = source.metadata.id.split(".", 1)[1] if "." in source.metadata.id else ""
                    if file_name:
                        # 删除external目录中的文件
                        client = DremioClient()
                        external_dir = client.external_dir
                        if external_dir and (external_dir / file_name).exists():
                            (external_dir / file_name).unlink()
                            logger.info(f"已从Dremio external目录删除文件: {file_name}")
            except Exception as e:
                logger.warning(f"从Dremio中删除数据源失败: {e}")

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
