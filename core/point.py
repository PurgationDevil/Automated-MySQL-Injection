"""注入位：payload 到底放在 HTTP 请求的哪个位置。

sqli-labs 的关卡按注入位划分，这是比"用什么注入手法"更前置的问题：

    Less-1  ~ 10   GET   参数 id
    Less-11 ~ 16   POST  表单字段 uname
    Less-17 ~ 22   Cookie / User-Agent / Referer 等请求头

所以 Injector 不再写死 params={id: payload}，而是交给 InjectionPoint 决定。
换关卡只换一个类，注入逻辑完全不动。
"""
from dataclasses import dataclass


class InjectionPoint:
    """一种注入位置。子类实现 send()，把 value 放进自己的位置。"""

    name = "get"

    def __init__(self, key: str):
        self.key = key

    def send(self, client, url: str, value: str):
        raise NotImplementedError


class GetPoint(InjectionPoint):
    """URL 查询参数：?id=payload"""

    name = "get"

    def send(self, client, url, value):
        return client.send("GET", url, params={self.key: value})


class PostPoint(InjectionPoint):
    """POST 表单字段：uname=payload

    注意：sqli-labs 一些关卡还要求 passwd 等字段，缺字段只会产生 PHP notice，
    不影响 SQL 执行，所以这里只提交被注入的那一个字段。
    """

    name = "post"

    def send(self, client, url, value):
        return client.send("POST", url, data={self.key: value})


class CookiePoint(InjectionPoint):
    """Cookie 值：Cookie: uname=payload"""

    name = "cookie"

    def send(self, client, url, value):
        return client.send("GET", url, cookies={self.key: value})


class HeaderPoint(InjectionPoint):
    """请求头：User-Agent: payload / Referer: payload"""

    name = "header"

    def send(self, client, url, value):
        return client.send("GET", url, headers={self.key: value})


@dataclass(frozen=True)
class PointSpec:
    """命令行参数 -> 注入位实例。"""

    mode: str
    key: str

    def build(self) -> InjectionPoint:
        cls = POINTS.get(self.mode)
        if cls is None:
            raise ValueError(f"未知注入位: {self.mode}（可选 {'/'.join(POINTS)}）")
        return cls(self.key)


POINTS = {
    "get": GetPoint,
    "post": PostPoint,
    "cookie": CookiePoint,
    "header": HeaderPoint,
}
