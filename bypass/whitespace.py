from bypass.base import BaseTransform

class SpaceToCommentTransform(BaseTransform):
    # 空格 -> /**/， MySQL 空白绕过。
    name = "space_to_comment"

    def transform(self, payload: str) -> str:
        return payload.replace(" ", "/**/")


class SpaceToTabTransform(BaseTransform):
    name = "space_to_tab"

    def transform(self, payload: str) -> str:
        return payload.replace(" ", "\t")