from urllib.parse import quote
from bypass.base import BaseTransform

class UrlEncodeTransform(BaseTransform):
    name = "url_encode"

    def transform(self, payload: str) -> str:
        # safe='' 表示把所有特殊字符都编码
        return quote(payload, safe="")


class DoubleUrlEncodeTransform(BaseTransform):
    name = "double_url_encode"

    def transform(self, payload: str) -> str:
        return quote(quote(payload, safe=""), safe="")