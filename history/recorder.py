"""请求历史：把每一次注入请求记录成 JSONL 文件（一行一个 JSON）。

每次运行自动落盘 history/run_时间戳.jsonl，方便事后回放、调试和写报告。
"""
import json
from datetime import datetime
from pathlib import Path


class Recorder:
    def __init__(self, dirpath: str = "history"):
        self.dir = Path(dirpath)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        self.rows = []

    def log(self, stage: str, raw_payload: str, final_payload: str, result) -> None:
        """记录一次请求。result 是 transport.http_client.HttpResult。"""
        row = {
            "seq": len(self.rows) + 1,
            "time": datetime.now().isoformat(timespec="seconds"),
            "stage": stage,
            "raw_payload": raw_payload,
            "final_payload": final_payload,
            "url": result.url,
            "status": result.status_code,
            "elapsed_ms": round(result.elapsed_ms, 1),
            "response_len": len(result.text),
        }
        self.rows.append(row)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def stats(self) -> dict:
        """运行汇总：请求总数、成功数、平均耗时、各阶段请求数。"""
        total = len(self.rows)
        ok = sum(1 for r in self.rows if 200 <= r["status"] < 300)
        avg = sum(r["elapsed_ms"] for r in self.rows) / total if total else 0.0
        stages = {}
        for r in self.rows:
            stages[r["stage"]] = stages.get(r["stage"], 0) + 1
        return {"total": total, "ok": ok, "avg_ms": avg, "stages": stages}
