import sqlite3

from app.core.integrity_check import _table_columns


def test_table_columns_supports_quoted_table_names() -> None:
    con = sqlite3.connect(":memory:")
    try:
        table_name = 'odd"name;drop table users;--'
        escaped_name = table_name.replace('"', '""')
        con.execute(f'CREATE TABLE "{escaped_name}" ("id" INTEGER, "value" TEXT)')

        cols = _table_columns(con, table_name)

        assert cols == {"id", "value"}
    finally:
        con.close()
