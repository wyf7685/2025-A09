"""
数据源管理接口
"""

import asyncio
import contextlib
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, TypeAdapter

from app.const import UPLOAD_DIR
from app.core.config import settings
from app.core.datasource import DataSourceMetadata, create_dremio_source
from app.core.dremio import get_async_dremio_client
from app.log import logger
from app.schemas.dremio import AnyDatabaseConnection, DremioDatabaseType
from app.services.datasource import datasource_service, temp_file_service
from app.services.session import session_service

# 创建路由
router = APIRouter(prefix="/datasources")


class RegisterDataSourceResponse(BaseModel):
    source_id: str
    metadata: DataSourceMetadata


@router.post("/upload", response_model=RegisterDataSourceResponse)
async def upload_file(
    file: UploadFile | None = File(default=None),
    source_name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    cleaned_file_id: str | None = Form(default=None),  # 清洗后文件ID（可选）
    field_mappings: str | None = Form(default=None),  # JSON格式的字段映射（可选）
    is_cleaned: bool = Form(default=False),  # 标识是否为清洗后的数据
) -> dict[str, Any]:
    """
    上传CSV/Excel文件并创建数据源
    支持上传原始数据或清洗后的数据
    """
    try:
        # 如果提供了清洗后的文件路径，使用清洗后的数据
        if cleaned_file_id and (cleaned_file_path := temp_file_service.get(cleaned_file_id)):
            logger.info(f"使用清洗后的数据文件: {cleaned_file_path}")
            file_path = (UPLOAD_DIR / str(uuid.uuid4())).with_suffix(cleaned_file_path.suffix)
            cleaned_file_path.rename(file_path)
            await temp_file_service.delete(cleaned_file_id)
        elif not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        else:
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in {".csv", ".xlsx", ".xls"}:
                raise HTTPException(status_code=400, detail="Unsupported file format")

            file_path = UPLOAD_DIR / f"{uuid.uuid4()}{file_ext}"
            file_path.write_bytes(await file.read())
            logger.info(f"保存原始数据文件: {file_path}")

        # 解析字段映射（如果有）
        parsed_field_mappings = {}
        if field_mappings:
            try:
                parsed_field_mappings = TypeAdapter(dict[str, str]).validate_json(field_mappings)
                logger.info(f"应用字段映射: {parsed_field_mappings}")
            except ValueError as e:
                logger.warning(f"字段映射解析失败: {e}")

        dremio_source = await get_async_dremio_client().add_data_source_file(file_path)

        # 创建数据源，如果有字段映射则应用到描述中
        source = create_dremio_source(dremio_source, source_name, description)

        # 如果有字段映射，保存到数据源元数据中
        if parsed_field_mappings:
            source.metadata.column_description = parsed_field_mappings
            logger.info(f"保存字段映射到数据源元数据: {len(parsed_field_mappings)} 个映射")

        # 标记是否为清洗后的数据
        if is_cleaned:
            source.metadata.description += " [智能清洗后的数据]"
            logger.info("标记数据源为清洗后的数据")

        source_id, source = await datasource_service.register(source)

        return {"source_id": source_id, "metadata": source.metadata}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("上传文件失败")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}") from e


class UploadCleanedFileRequest(BaseModel):
    cleaned_file_id: str
    source_name: str
    description: str | None = None
    field_mappings: dict[str, str] | None = None
    cleaning_summary: str | None = None  # 清洗操作总结


@router.post("/upload-cleaned", response_model=RegisterDataSourceResponse)
async def upload_cleaned_file(request: UploadCleanedFileRequest) -> dict[str, Any]:
    """
    上传智能清洗后的数据文件
    """
    try:
        if not request.cleaned_file_id or not (cleaned_file_path := temp_file_service.get(request.cleaned_file_id)):
            raise HTTPException(status_code=400, detail="No cleaned file provided")

        # 保存清洗后的文件
        file_path = UPLOAD_DIR / f"{uuid.uuid4()}{cleaned_file_path.suffix}"
        cleaned_file_path.rename(file_path)
        await temp_file_service.delete(request.cleaned_file_id)

        dremio_source = await get_async_dremio_client().add_data_source_file(file_path)

        # 创建数据源
        source = create_dremio_source(dremio_source, request.source_name, request.description)

        # 应用字段映射
        source.metadata.column_description = request.field_mappings

        # 添加清洗标记和总结
        clean_description = "[智能清洗后的数据]"
        if request.cleaning_summary:
            clean_description += f" 清洗总结: {request.cleaning_summary}"

        if source.metadata.description:
            source.metadata.description += " " + clean_description
        else:
            source.metadata.description = clean_description

        source_id, source = await datasource_service.register(source)

        logger.info(
            f"成功上传清洗后的数据: {request.source_name}, 应用了 {len(request.field_mappings or {})} 个字段映射"
        )

        return {"source_id": source_id, "metadata": source.metadata}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("上传清洗后的文件失败")
        raise HTTPException(status_code=500, detail=f"Failed to upload cleaned file: {e}") from e


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
        dremio_source = await get_async_dremio_client().add_data_source_database(
            request.database_type, request.connection
        )
        source = create_dremio_source(dremio_source)
        source_id, source = await datasource_service.register(source)
        if request.name:
            source.metadata.name = request.name
        if request.description:
            source.metadata.description = request.description
        await datasource_service.save_source(source_id, source)
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
        if not await datasource_service.source_exists(source_id):
            raise HTTPException(status_code=404, detail="Datasource not found")

        source = await datasource_service.get_source(source_id)

        # 更新元数据
        if data.name is not None:
            source.metadata.name = data.name

        if data.description is not None:
            source.metadata.description = data.description

        await datasource_service.save_source(source_id, source)
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
                await datasource_service.sync_from_dremio()
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
        if not await datasource_service.source_exists(source_id):
            raise HTTPException(status_code=404, detail="Datasource not found")
        return (await datasource_service.get_source(source_id)).metadata

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
        if not await datasource_service.source_exists(source_id):
            raise HTTPException(status_code=404, detail="Datasource not found")

        source = await datasource_service.get_source(source_id)
        logger.info(f"获取数据源数据: {source_id}, 类型: {source.metadata.source_type}")

        # 检查数据源是否可用
        try:
            # 如果是Dremio数据源，先检查文件是否存在
            if source.metadata.source_type.startswith("dremio"):
                from app.core.datasource.dremio import DremioDataSource

                if isinstance(source, DremioDataSource):
                    dremio_source = source.get_source()
                    if (
                        len(dremio_source.path) == 2
                        and dremio_source.path[0] == settings.DREMIO_EXTERNAL_NAME
                        and dremio_source.type == "FILE"
                    ):
                        file_name = dremio_source.path[1]
                        file_path = settings.DREMIO_EXTERNAL_DIR / file_name
                        if not file_path.exists():
                            logger.error(f"数据源文件不存在: {file_path}")
                            # 立即清理这个数据源
                            await datasource_service.delete_source(source_id)
                            raise HTTPException(status_code=404, detail=f"数据源文件已被删除: {file_name}")

            # 获取形状信息
            rows, cols = source.get_shape()
            logger.info(f"数据源形状: {rows} 行 × {cols} 列")

            if rows == 0:
                logger.warning(f"数据源 {source_id} 没有数据")
                return {
                    "data": [],
                    "total": 0,
                    "skip": skip,
                    "limit": limit,
                }

            # 获取数据
            data = source.get_data(limit + skip)
            logger.info(f"成功获取数据: {len(data)} 行")

            if skip > 0:
                data = data.iloc[skip:]
                logger.info(f"跳过 {skip} 行后剩余: {len(data)} 行")

            return {
                "data": data.to_dict(orient="records"),
                "total": rows,
                "skip": skip,
                "limit": limit,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取数据源数据失败: {e}")
            raise HTTPException(status_code=500, detail=f"数据源不可用: {e}") from e

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
    if not await datasource_service.source_exists(source_id):
        raise HTTPException(status_code=404, detail="Datasource not found")

    try:
        source = await datasource_service.get_source(source_id)

        # 如果是Dremio数据源，尝试从Dremio中删除
        if source.metadata.source_type.startswith("dremio"):
            try:
                # 获取DremioDataSource对象
                from app.core.datasource.dremio import DremioDataSource

                if isinstance(source, DremioDataSource):
                    dremio_source = source.get_source()
                    # 检查是否是external目录中的文件
                    if (
                        len(dremio_source.path) == 2
                        and dremio_source.path[0] == settings.DREMIO_EXTERNAL_NAME
                        and dremio_source.type == "FILE"
                    ):
                        # 从external目录中删除文件
                        file_name = dremio_source.path[1]
                        file_path = settings.DREMIO_EXTERNAL_DIR / file_name
                        if file_path.exists():
                            file_path.unlink()
                            logger.info(f"已从external目录删除文件: {file_name}")
                        else:
                            logger.warning(f"文件不存在: {file_path}")

                        client = get_async_dremio_client()

                        # 方法1：尝试直接删除数据源
                        delete_success = await client.delete_data_source(dremio_source.path)
                        if delete_success:
                            logger.info(f"成功从Dremio中删除数据源: {dremio_source.path}")
                        else:
                            logger.warning(f"从Dremio中删除数据源失败: {dremio_source.path}")

                        # 方法2：刷新external数据源，让Dremio重新扫描
                        refresh_success = await client.refresh_external_source()
                        if refresh_success:
                            logger.info("成功刷新external数据源")
                        else:
                            logger.warning("刷新external数据源失败")

                        # 无论是否成功，都等待一段时间让Dremio处理
                        await asyncio.sleep(2)

                    else:
                        logger.info(f"跳过删除非external文件类型的数据源: {dremio_source.type}")
                else:
                    logger.warning(f"数据源不是DremioDataSource类型: {type(source)}")
            except Exception as e:
                logger.warning(f"从Dremio中删除数据源失败: {e}")

        # 从数据源字典中删除
        await datasource_service.delete_source(source_id)

        # 删除关联的会话
        # TODO: 考虑其他删除方式
        for session in list(session_service.sessions.values()):
            if source_id in session.dataset_ids:
                await session_service.delete(session.id)

        return {"success": True, "message": f"Datasource {source_id} deleted"}

    except Exception as e:
        logger.exception("删除数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to delete datasource: {e}") from e
