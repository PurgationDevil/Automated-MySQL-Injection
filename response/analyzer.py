"""响应分析：只做三件事——

1. 判断响应里有没有 SQL 报错（报错注入的信号）
2. 比较两个页面像不像（布尔盲注的信号）
3. 从页面里提取 ^^...$$ 标记包裹的数据（UNION 回显提取）
"""
import re
from difflib import SequenceMatcher

# MySQL 常见报错特征（sqli-labs 里最常见的是前两条）
SQL_ERROR_PATTERNS = [
    r"you have an error in your sql syntax",
    r"unknown column",
    r"warning.{0,40}mysql",
    r"mysql_fetch",
    r"mysqli?_[a-z_]+\(\)",
    r"check the manual that (corresponds to|your)",
]
_SQL_ERROR_RE = re.compile("|".join(SQL_ERROR_PATTERNS), re.IGNORECASE)

# ^^数据$$ 提取：payload 里用 concat(0x5e5e, ..., 0x2424) 包一层，
# 不管页面长什么样，都能用正则把数据抠出来
_SENTINEL_RE = re.compile(r"\^\^(.*?)\$\$", re.DOTALL)


def has_sql_error(text: str) -> bool:
    """响应文本里是否出现 SQL 报错特征。"""
    return bool(_SQL_ERROR_RE.search(text))


def ratio(a: str, b: str) -> float:
    """页面相似度 0~1，1 表示完全相同。"""
    return SequenceMatcher(None, a, b).ratio()


def pages_same(a: str, b: str, ratio_threshold: float = 0.985, len_threshold: float = 0.02) -> bool:
    """判断两个页面是否“看起来一样”。

    同时看相似度和相对长度差：页面大部分是 HTML 模板，
    只差一小块内容时相似度仍然很高，所以长度差也要一并检查。
    """
    if a == b:
        return True
    if abs(len(a) - len(b)) / max(len(a), len(b), 1) > len_threshold:
        return False
    return ratio(a, b) >= ratio_threshold


def extract_sentinel(text: str):
    """提取 ^^value$$ 中的 value；没找到返回 None（区分“空值”和“没回显”）。"""
    m = _SENTINEL_RE.search(text)
    return m.group(1) if m else None
