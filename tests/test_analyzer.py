"""响应分析模块的离线单元测试（不需要网络）。

运行：python tests/test_analyzer.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from response.analyzer import extract_sentinel, has_sql_error, pages_same, ratio

# sqli-labs Less-1 真实报错页片段
ERROR_PAGE = (
    "<html><font size='3' >You have an error in your SQL syntax; "
    "check the manual that corresponds to your MySQL server version "
    "for the right syntax to use near ''1'' LIMIT 0,1' at line 1</font></html>"
)
NORMAL_PAGE = (
    "<html><font size='3'>Your Login name:dummy</font><br>"
    "<font size='3'>Your Password:dummy</font></html>"
)
EMPTY_PAGE = "<html><font size='3'></font></html>"


def test_error_detected():
    assert has_sql_error(ERROR_PAGE)


def test_unknown_column_detected():
    assert has_sql_error("Unknown column '4' in 'order clause'")


def test_no_false_positive():
    assert not has_sql_error(NORMAL_PAGE)


def test_pages_same_identical():
    assert pages_same(NORMAL_PAGE, NORMAL_PAGE)


def test_pages_same_tiny_diff():
    # 只多一个空格：应视为“相同”
    assert pages_same(NORMAL_PAGE, NORMAL_PAGE + " ")


def test_pages_different():
    # 少了一大块登录信息：应视为“不同”
    assert not pages_same(NORMAL_PAGE, EMPTY_PAGE)


def test_ratio_order():
    assert ratio(NORMAL_PAGE, NORMAL_PAGE) == 1.0
    assert ratio(NORMAL_PAGE, EMPTY_PAGE) < ratio(NORMAL_PAGE, NORMAL_PAGE + " ")


def test_extract_sentinel():
    assert extract_sentinel("xx <font>^^security$$</font> yy") == "security"


def test_extract_sentinel_empty_value():
    assert extract_sentinel("^^$$") == ""


def test_extract_sentinel_not_found():
    assert extract_sentinel("no marker here") is None


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
