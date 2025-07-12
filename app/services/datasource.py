import json
import threading
import uuid

from app.const import DATASOURCE_DIR
from app.core.datasource import DataSource, create_dremio_source, deserialize_data_source
from app.core.dremio import get_dremio_client
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
                self.load_source(fp.stem)
            except Exception as e:
                logger.opt(exception=True).warning(f"Failed to load data source from {fp}: {e}")

    def load_source(self, source_id: str) -> DataSource:
        fp = DATASOURCE_DIR / f"{source_id}.json"
        if not fp.exists():
            raise FileNotFoundError(f"Data source file {fp} does not exist")

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

        current_ds = {s.unique_id: i for i, s in self.sources.items() if s.unique_id.startswith("dremio:")}
        for ds in dss:
            source = create_dremio_source(ds)
            if source.unique_id not in current_ds:
                source_id = str(uuid.uuid4())
                self.save_source(source_id, source)
            else:
                current_ds.pop(source.unique_id)
        for source_id in current_ds.values():
            self.delete_source(source_id)

    def register(self, source: DataSource) -> str:
        """
        注册数据源

        Args:
            source: 数据源对象

        Returns:
            str: 数据源ID
        """
        for source_id, existing_source in self.sources.items():
            if existing_source.unique_id == source.unique_id:
                return source_id

        source_id = str(uuid.uuid4())
        self.save_source(source_id, source)
        return source_id


datasource_service = DataSourceService()
datasource_service.load_sources()
threading.Thread(target=datasource_service.sync_from_dremio).start()
