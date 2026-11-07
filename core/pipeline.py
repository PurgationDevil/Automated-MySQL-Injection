from typing import Iterable
from bypass.base import BaseTransform

def apply_transforms(payload: str, transforms: Iterable[BaseTransform]) -> str:
    # 按顺序执行变换管线。
    result = payload
    for t in transforms:
        before = result
        result = t.transform(result)
        print(f"[{t.name}] {before!r} -> {result!r}")
    return result
