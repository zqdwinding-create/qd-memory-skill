#!/usr/bin/env python3
"""
L6 增量捕捉 — bash 可直接调，不靠 LLM

流程：
1. 读今天的 daily log（追加前一天最后 1h）
2. 调 tacit-knowledge-catcher.py --mode catch --input <拼接文本>
3. 报告结果

由 L6 增量更新 cron 调用。
"""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
WORKSPACE = Path.home() / ".openclaw/workspace"
SK_PATH = WORKSPACE / "shared-knowledge.json"
MEMORY_DIR = WORKSPACE / "memory"
TKC = WORKSPACE / "scripts" / "tacit-knowledge-catcher.py"


def get_today_daily_log() -> str:
    """读今天 + 昨天 daily log"""
    today = NOW.strftime("%Y-%m-%d")
    yesterday = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")
    texts = []
    for d in [yesterday, today]:
        f = MEMORY_DIR / f"{d}.md"
        if f.exists():
            texts.append(f.read_text(encoding="utf-8"))
    return "\n".join(texts)


def main():
    # 1. 读 daily log
    text = get_today_daily_log()
    if len(text) < 200:
        print(f"⏸️ daily log 太短（{len(text)} chars），跳过")
        return 0

    # 2. 调 tkc catch
    source = f"cron-l6-catch-{NOW.strftime('%Y%m%d%H%M')}"
    result = subprocess.run(
        ["python3", str(TKC), "--mode", "catch", "--input", text, "--source", source],
        capture_output=True, text=True, timeout=60
    )
    print("tkc stdout:", result.stdout)
    if result.returncode != 0:
        print("tkc stderr:", result.stderr, file=sys.stderr)
        return 1

    # 3. 健康度
    sk = json.loads(SK_PATH.read_text(encoding="utf-8"))
    print(f"✅ L6 总条数: {len(sk['entries'])}, updated: {sk['updated']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
