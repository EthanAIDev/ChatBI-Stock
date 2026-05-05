from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class QueryEngine(ABC):
    @abstractmethod
    def execute(self, sql: str) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_tables(self) -> list[str]:
        ...

    @abstractmethod
    def get_schema(self, table_name: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def validate_sql(self, sql: str) -> str:
        ...

    @abstractmethod
    def get_connection_info(self) -> dict[str, Any]:
        ...


class QueryEngineFactory:
    _registry: dict[str, type[QueryEngine]] = {}

    @classmethod
    def register(cls, name: str, engine_cls: type[QueryEngine]) -> None:
        cls._registry[name] = engine_cls

    @classmethod
    def create(cls, name: str, **kwargs) -> QueryEngine:
        engine_cls = cls._registry.get(name)
        if not engine_cls:
            raise ValueError(f'未注册的查询引擎: {name}，可用: {list(cls._registry.keys())}')
        return engine_cls(**kwargs)
