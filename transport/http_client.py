from dataclasses import dataclass
from typing import Any, Optional
import requests


@dataclass
class HttpResult:
    status_code: int
    elapsed_ms: float
    headers: dict
    text: str
    url: str


class HttpClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def send(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        headers: Optional[dict] = None,
        cookies: Optional[dict] = None,
    ) -> HttpResult:
        resp = requests.request(
            method=method.upper(),
            url=url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=self.timeout,
            # 实验环境可关校验；正式环境别这么干
            verify=False,
        )
        return HttpResult(
            status_code=resp.status_code,
            elapsed_ms=resp.elapsed.total_seconds() * 1000,
            headers=dict(resp.headers),
            text=resp.text,
            url=str(resp.url),
        )
