"""bypass 变换与管线的离线单元测试（不需要网络）。

运行：python tests/test_transforms.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bypass.encoding import DoubleUrlEncodeTransform, UrlEncodeTransform
from bypass.whitespace import SpaceToCommentTransform, SpaceToTabTransform
from core.pipeline import apply_transforms


def test_space_to_comment():
    t = SpaceToCommentTransform()
    assert t.transform("union select 1,2,3") == "union/**/select/**/1,2,3"


def test_space_to_tab():
    assert SpaceToTabTransform().transform("a b") == "a\tb"


def test_url_encode():
    out = UrlEncodeTransform().transform("a b'")
    assert out == "a%20b%27"


def test_double_url_encode():
    # 第一次编码后 ' -> %27，第二次 % 也被编码 -> %2527
    out = DoubleUrlEncodeTransform().transform("'")
    assert out == "%2527"


def test_pipeline_order():
    # 先空格->/**/，再整体 URL 编码：最终不应含裸空格或裸 /
    out = apply_transforms("union select 1",
                           [SpaceToCommentTransform(), UrlEncodeTransform()])
    assert " " not in out
    assert "/" not in out
    assert "%2F%2A%2A%2F" in out  # /**/ 的编码形态


def test_pipeline_empty():
    assert apply_transforms("1' and 1=1", []) == "1' and 1=1"


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
