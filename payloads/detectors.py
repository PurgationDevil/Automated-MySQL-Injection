"""阶段 1：注入点探测。

两种最基础的探测方式，互为补充：
    报错探测：直接发一个单引号 1'，看响应里有没有 SQL 报错
    布尔探测：and 1=1 的页面应与正常页相同，and 1=2 的页面应明显不同
"""
from response import analyzer


def detect_error(injector):
    """发 payload "1'"，返回 (是否报错, HttpResult)。"""
    result = injector.inject(statement="", suffix="", stage="probe_quote")
    return analyzer.has_sql_error(result.text), result


def detect_boolean(injector):
    """三页面对比，返回 (布尔注入是否成立, 相似度信息)。"""
    normal = injector.inject(statement="", prefix="1", suffix="", stage="probe_normal")
    page_true = injector.inject("and 1=1", stage="probe_true")
    page_false = injector.inject("and 1=2", stage="probe_false")

    ok = (
        analyzer.pages_same(page_true.text, normal.text)
        and not analyzer.pages_same(page_false.text, normal.text)
    )
    info = {
        "normal_vs_true": analyzer.ratio(normal.text, page_true.text),
        "normal_vs_false": analyzer.ratio(normal.text, page_false.text),
    }
    return ok, info
