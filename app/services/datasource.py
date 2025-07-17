import json
import threading
import uuid
from pathlib import Path

from app.const import DATASOURCE_DIR
from app.core.datasource import DataSource, create_dremio_source, deserialize_data_source
from app.core.dremio import get_dremio_client
from app.core.lifespan import lifespan
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
            dss = get_dremio_client().list_sources()

        current_ds = {
            source.unique_id: source_id
            for source_id, source in self.sources.items()
            if source.unique_id.startswith("dremio:")
        }
        for dremio_source in dss:
            source = create_dremio_source(dremio_source)
            if source.unique_id not in current_ds:
                source_id = str(uuid.uuid4())
                self.save_source(source_id, source)
            else:
                current_ds.pop(source.unique_id)
        for source_id in current_ds.values():
            self.delete_source(source_id)
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
            tuple[str, DataSource]: 数据源 ID 和数据源对象
        """
        gen = (source_id for source_id, source in self.sources.items() if source.unique_id == source.unique_id)
        if existing := next(gen, None):
            return existing, self.sources[existing]

        source_id = str(uuid.uuid4())
        self.save_source(source_id, source)
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
