from abc import ABC, abstractmethod

class BaseTransform(ABC):
    # 所有绕过规则的统一接口。

    name: str = "base"

    @abstractmethod
    def transform(self, payload: str) -> str:
        # 输入原始 payload，输出变换后的字符串。
        raise NotImplementedError
