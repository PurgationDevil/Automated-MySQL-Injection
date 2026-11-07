"""语法变体与注入位的离线测试（不需要网络）。

运行：python tests/test_syntax.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bypass.syntax import Dialect, candidates
from core.point import PointSpec, GetPoint, PostPoint, CookiePoint, HeaderPoint


def _pick(label, only="auto"):
    return [d for d in candidates(only) if d.label == label][0]


def test_plain_rendering():
    d = Dialect()
    assert d.and_cond("1=1") == "and 1=1"
    assert d.substr("(SELECT 1)", 1, 1) == "substr((SELECT 1),1,1)"
    assert d.ge("length(x)", 3) == "(length(x)>=3)"


def test_space_comment_replaces_every_space():
    d = _pick("space_comment", "space")
    assert d.and_cond("1=1") == "and/**/1=1"


def test_and_amp_avoids_and_keyword():
    d = _pick("and_amp", "and")
    assert d.and_cond("1=1") == "&& 1=1"
    assert "and" not in d.and_cond("1=1")


def test_no_comma_uses_from_for():
    d = _pick("no_comma", "comma")
    assert d.substr("(SELECT 1)", 2, 1) == "substr((SELECT 1) from 2 for 1)"
    assert "," not in d.substr("(SELECT 1)", 2, 1)


def test_between_replaces_greater_than():
    d = _pick("between")
    assert "between" in d.gt("1", 5)
    assert ">" not in d.gt("1", 5).replace("between", "")


def test_candidates_auto_starts_plain():
    assert candidates()[0].label == "plain"


def test_point_spec_builds_right_class():
    assert isinstance(PointSpec("get", "id").build(), GetPoint)
    assert isinstance(PointSpec("post", "uname").build(), PostPoint)
    assert isinstance(PointSpec("cookie", "uname").build(), CookiePoint)
    assert isinstance(PointSpec("header", "User-Agent").build(), HeaderPoint)


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
