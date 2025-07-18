import json
import threading
import uuid
from pathlib import Path

from app.const import DATASOURCE_DIR
from app.core.datasource import DataSource, create_dremio_source, deserialize_data_source
from app.core.dremio import get_dremio_client
from app.core.lifespan import lifespan
from app.log import logger
from app.core.config import settings

_dremio_sync_sem = threading.Semaphore(1)


class DataSourceService:
    def __init__(self) -> None:
        self.sources: dict[str, DataSource] = {}

    def source_exists(self, source_id: str) -> bool:
        if source_id in self.sources:
            return True
        try:
            self.load_source(source_id)
            return True
        except FileNotFoundError:
            return False

    def load_sources(self) -> None:
        for fp in DATASOURCE_DIR.iterdir():
            if not (fp.is_file() and fp.suffix == ".json"):
                continue
            try:
                self.load_source(fp)
            except Exception as e:
                logger.opt(exception=True).warning(f"Failed to load data source from {fp}: {e}")
        self._check_unique()

    def load_source(self, source_id: str | Path) -> DataSource:
        fp = DATASOURCE_DIR / f"{source_id}.json" if isinstance(source_id, str) else source_id
        if not fp.exists():
            raise FileNotFoundError(f"Data source file {fp} does not exist")

        source_id = source_id.stem if isinstance(source_id, Path) else source_id
        try:
            data = json.loads(fp.read_text())
            source = deserialize_data_source(data["type"], data["data"])
            self.sources[source_id] = source
            return source
        except Exception as e:
            raise ValueError(f"Failed to load data source from {fp}: {e}") from e

    def save_source(self, source_id: str, source: DataSource) -> None:
        fp = DATASOURCE_DIR / f"{source_id}.json"
        data = dict(zip(("type", "data"), source.serialize(), strict=True))
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        self.sources[source_id] = source

    def get_source(self, source_id: str) -> DataSource:
        if source_id in self.sources:
            return self.sources[source_id]
        return self.load_source(source_id)

    def delete_source(self, source_id: str) -> None:
        if (fp := DATASOURCE_DIR / f"{source_id}.json").exists():
            fp.unlink()
        self.sources.pop(source_id, None)

    def sync_from_dremio(self) -> None:
        with _dremio_sync_sem:
            try:
                dss = get_dremio_client().list_sources()
            except Exception as e:
                logger.warning(f"从Dremio获取数据源列表失败: {e}")
                return

        current_ds = {
            source.unique_id: source_id
            for source_id, source in self.sources.items()
            if source.unique_id.startswith("dremio:")
        }
        
        # 记录从Dremio获取的数据源
        dremio_unique_ids = set()
        
        # 添加从Dremio获取的数据源
        for dremio_source in dss:
            try:
                source = create_dremio_source(dremio_source)
                dremio_unique_ids.add(source.unique_id)
                
                if source.unique_id not in current_ds:
                    source_id = str(uuid.uuid4())
                    self.save_source(source_id, source)
                    logger.debug(f"添加新的Dremio数据源: {source.unique_id}")
                else:
                    # 数据源已存在，从待删除列表中移除
                    current_ds.pop(source.unique_id)
            except Exception as e:
                logger.warning(f"处理Dremio数据源失败: {dremio_source}, 错误: {e}")
                continue
        
        # 删除不在Dremio中的数据源（但要谨慎处理）
        for unique_id, source_id in current_ds.items():
            if unique_id not in dremio_unique_ids:
                try:
                    source = self.get_source(source_id)
                    # 如果是文件类型的数据源，检查文件是否还存在
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
                            if file_path.exists():
                                # 文件存在但Dremio中没有，可能是缓存问题，不删除
                                logger.warning(f"文件存在但Dremio中未找到，跳过删除: {file_name}")
                                continue
                    
                    # 如果文件不存在，删除数据源
                    self.delete_source(source_id)
                    logger.info(f"删除不存在的Dremio数据源: {source_id}")
                except Exception as e:
                    logger.warning(f"处理数据源删除失败: {source_id}, 错误: {e}")
                    
        self._check_unique()

    def cleanup_deleted_sources(self) -> None:
        """
        清理已删除的数据源，检查文件是否存在
        """
        sources_to_delete = []
        
        for source_id, source in self.sources.items():
            if source.metadata.source_type.startswith("dremio"):
                try:
                    # 检查是否是DremioDataSource
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
                                logger.info(f"发现已删除的文件，将清理数据源: {source_id} -> {file_name}")
                                sources_to_delete.append(source_id)
                except Exception as e:
                    logger.warning(f"检查数据源文件时出错: {source_id}, {e}")
        
        # 删除已删除的数据源
        for source_id in sources_to_delete:
            try:
                self.delete_source(source_id)
                logger.info(f"已清理删除的数据源: {source_id}")
            except Exception as e:
                logger.warning(f"清理数据源失败: {source_id}, {e}")

    def _check_unique(self) -> None:
        """检查数据源的唯一性"""
        unique_ids = set()
        for source_id, source in list(self.sources.items()):
            if source.unique_id in unique_ids:
                del self.sources[source_id]
            unique_ids.add(source.unique_id)

    def register(self, source: DataSource) -> tuple[str, DataSource]:
        """
        注册数据源

        Args:
            source: 数据源对象

        Returns:
            tuple[str, DataSource]: (数据源ID, 数据源对象)
        """
        # 检查是否已存在相同的数据源
        for existing_id, existing_source in self.sources.items():
            if existing_source.unique_id == source.unique_id:
                logger.info(f"数据源已存在，返回现有ID: {existing_id}")
                return existing_id, existing_source
        
        # 生成新的数据源ID
        source_id = str(uuid.uuid4())
        self.save_source(source_id, source)
        logger.info(f"注册新数据源: {source_id} -> {source.unique_id}")
        return source_id, source


datasource_service = DataSourceService()


@lifespan.on_startup
def _() -> None:
    """在应用启动时加载数据源"""

    datasource_service.load_sources()
    logger.opt(colors=True).success(f"加载 <y>{len(datasource_service.sources)}</> 个数据源")

    def sync() -> None:
        try:
            datasource_service.sync_from_dremio()
        except Exception:
            logger.exception("从 Dremio 同步数据源失败")
        else:
            logger.success("成功从 Dremio 同步数据源")

    threading.Thread(target=sync, daemon=True).start()
