import json
import threading
import uuid
from pathlib import Path

from app.const import DATASOURCE_DIR, TEMP_DIR
from app.core.config import settings
from app.core.datasource import DataSource, create_dremio_source, deserialize_data_source
from app.core.datasource.dremio import DremioDataSource
from app.core.dremio import get_dremio_client
from app.core.lifespan import lifespan
from app.exception import DataSourceLoadFailed, DataSourceNotFound
from app.log import logger

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
            raise DataSourceNotFound(source_id if isinstance(source_id, str) else "<Unknown>")

        source_id = source_id.stem if isinstance(source_id, Path) else source_id
        try:
            data = json.loads(fp.read_text())
            source = deserialize_data_source(data["type"], data["data"])
        except Exception as e:
            raise DataSourceLoadFailed(source_id) from e

        self.sources[source_id] = source
        return source

    def save_source(self, source_id: str, source: DataSource) -> None:
        fp = DATASOURCE_DIR / f"{source_id}.json"
        type_, data_ = source.serialize()
        fp.write_text(json.dumps({"type": type_, "data": data_}, ensure_ascii=False, indent=2))
        self.sources[source_id] = source

    def get_source(self, source_id: str) -> DataSource:
        if source_id in self.sources:
            return self.sources[source_id]
        return self.load_source(source_id)

    def delete_source(self, source_id: str) -> None:
        if not self.source_exists(source_id):
            raise DataSourceNotFound(source_id)

        if (fp := DATASOURCE_DIR / f"{source_id}.json").exists():
            try:
                fp.unlink()
            except Exception as e:
                logger.warning(f"删除数据源文件失败: {fp} - {e}")

        self.sources.pop(source_id, None)

    def sync_from_dremio(self) -> None:
        with _dremio_sync_sem:
            logger.info("从 Dremio 同步数据源...")
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
        dremio_unique_ids: set[str] = set()

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


class TempFileService:
    def __init__(self) -> None:
        self._data: dict[str, Path] = {}

    def register(self, file_path: Path) -> str:
        """
        注册临时文件

        Args:
            file_path: 临时文件路径

        Returns:
            str: 临时文件ID
        """
        file_id = str(uuid.uuid4())
        temp_path = TEMP_DIR / f"{file_id}{file_path.suffix}"
        file_path.rename(temp_path)
        self._data[file_id] = temp_path
        return file_id

    def get(self, file_id: str) -> Path | None:
        """
        获取临时文件路径

        Args:
            file_id: 临时文件ID

        Returns:
            Path | None: 临时文件路径，如果不存在则返回None
        """
        return self._data.get(file_id)

    def delete(self, file_id: str) -> None:
        """
        删除临时文件

        Args:
            file_id: 临时文件ID
        """
        if (file_path := self._data.get(file_id)) and file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.warning(f"删除临时文件失败: {file_path} - {e}")
            del self._data[file_id]

    def delete_all(self) -> None:
        """
        删除所有临时文件
        """
        for file_id in list(self._data):
            self.delete(file_id)


class TempSourceService:
    def __init__(self) -> None:
        self._data: dict[str, DataSource] = {}

    def register(self, source: DataSource) -> str:
        """
        注册临时数据源

        Args:
            source: 数据源对象

        Returns:
            str: 临时数据源ID
        """
        source_id = str(uuid.uuid4())
        self._data[source_id] = source
        return source_id

    def get(self, source_id: str) -> DataSource | None:
        """
        获取临时数据源

        Args:
            source_id: 临时数据源ID

        Returns:
            DataSource | None: 数据源对象，如果不存在则返回None
        """
        return self._data.get(source_id)

    def delete(self, source_id: str) -> None:
        """
        删除临时数据源

        Args:
            source_id: 临时数据源ID
        """
        self._data.pop(source_id, None)


datasource_service = DataSourceService()
temp_file_service = TempFileService()
temp_source_service = TempSourceService()


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


@lifespan.on_shutdown
def _() -> None:
    """在应用关闭时清理临时文件和数据源"""
    logger.info("清理所有临时文件...")
    temp_file_service.delete_all()
