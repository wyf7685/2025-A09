from dataclasses import dataclass


@dataclass
class DremioSource:
    id: str
    path: list[str]
    type: str


@dataclass
class DremioContainer:
    id: str
    path: list[str]
