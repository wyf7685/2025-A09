from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


@dataclass
class DremioSource:
    id: str
    path: list[str]
    type: str


@dataclass
class DremioContainer:
    id: str
    path: list[str]


type DremioDatabaseType = Literal["MSSQL", "MYSQL", "ORACLE", "POSTGRES"]


class BaseDatabaseConnection(BaseModel):
    hostname: str
    port: int
    username: str
    password: str


class MSSQLConnection(BaseDatabaseConnection):
    pass


class MySQLConnection(BaseDatabaseConnection):
    pass


class PostgreSQLConnection(BaseDatabaseConnection):
    databaseName: str  # noqa: N815
    authenticationType: Literal["MASTER"] = "MASTER"  # noqa: N815


class OracleConnection(BaseDatabaseConnection):
    instance: str


type AnyDatabaseConnection = MSSQLConnection | MySQLConnection | PostgreSQLConnection | OracleConnection
