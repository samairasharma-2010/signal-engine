"""
Tiny SQLite helper. Two separate databases are kept so synthetic test data
can never be mixed up with real data:

    data/demo.db   synthetic data, used to test the pipeline
    data/live.db   real data fetched from the internet
"""
import sqlite3
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def db_path(mode: str) -> Path:
    if mode not in ("demo", "live"):
        raise ValueError("mode must be 'demo' or 'live'")
    return DATA_DIR / f"{mode}.db"


def connect(mode: str) -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    return sqlite3.connect(db_path(mode))


def read_table(mode: str, table: str) -> pd.DataFrame:
    con = connect(mode)
    try:
        return pd.read_sql(f"SELECT * FROM {table}", con)
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


def write_table(mode: str, table: str, df: pd.DataFrame) -> None:
    """Replace a whole table."""
    con = connect(mode)
    try:
        df.to_sql(table, con, if_exists="replace", index=False)
    finally:
        con.close()


def upsert(mode: str, table: str, df: pd.DataFrame, keys: list[str]) -> None:
    """Add rows, replacing any existing row with the same key columns.
    Dates must already be strings (YYYY-MM-DD) so old and new rows compare."""
    old = read_table(mode, table)
    combined = pd.concat([old, df], ignore_index=True) if not old.empty else df
    combined = combined.drop_duplicates(subset=keys, keep="last")
    write_table(mode, table, combined)
