from sqlmat.adapters.base import SOURCE_TABLE_ALIAS, TARGET_TABLE_ALIAS
from sqlmat.adapters.duckdb import DuckDBAdapter
from sqlmat.adapters.redshift import RedshiftAdapter

__all__ = ["DuckDBAdapter", "RedshiftAdapter", "SOURCE_TABLE_ALIAS", "TARGET_TABLE_ALIAS"]
