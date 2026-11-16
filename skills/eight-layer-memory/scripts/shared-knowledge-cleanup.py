#!/usr/bin/env python3
"""
shared-knowledge.json 信噪比清理脚本
把 L6 低质量条目归档到 shared-knowledge-archive.json，**不删除原数据**

开源脱敏版（2026-11-16 自生产版回填）：不含真实定时任务 ID / 人名 / 机器特定路径。

历史问题（2026-06-09 复盘发现，量级为数百条规模）：
- 大量条目 type 字段错位（如旧 conclusion 前缀格式的 id 配了错位的 type）
- 多条有 answer 字段没 conclusion 字段（system-config/capability 字段错位）
- 关键内容 < 20 字 = 低信号
- updated 超过 60 天 = stale

用法：
  python3 shared-knowledge-cleanup.py            # 默认 dry-run，只打印报告
  python3 shared-knowledge-cleanup.py --apply    # 实际归档低分条目
  python3 shared-knowledge-cleanup.py --threshold 30  # 自定义归档阈值（默认 30）
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
WORKSPACE = Path.home() / ".openclaw/workspace"
SK_PATH = WORKSPACE / "shared-knowledge.json"
ARCHIVE_PATH = WORKSPACE / "shared-knowledge-archive.json"
LOG_DIR = WORKSPACE / "memory/logs"

# 合法 type 集合
VALID_TYPES = {"system-config", "capability", "project-state", "conversation-topic"}


def log(msg: str) -> None:
    """统一打印"""
    ts = NOW.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def score_entry(entry: dict) -> tuple[int, list[str]]:
    """
    评估单条 entry 质量分（0-100），返回 (score, reasons)
    < 30 = 建议归档
    """
    reasons = []
    score = 100
    dtype = entry.get("type", "")
    fields = set(entry.keys())

    # 1. type 合法性（错位直接归档：id 前缀与 type 不一致，例 id=con-xxx type=conclusion）
    if dtype not in VALID_TYPES:
        score -= 100  # type 非法 → 必归档
        reasons.append(f"type 非法（{dtype}，应是 {VALID_TYPES}）")
    else:
        # type 合法但 id 前缀与 type 不匹配（数据污染信号）
        eid = entry.get("id", "")
        expected_prefix = {"system-config": "sys", "capability": "cap", "project-state": "pro", "conversation-topic": "con"}.get(dtype)
        if eid and expected_prefix and not eid.startswith(expected_prefix):
            score -= 50
            reasons.append(f"id 前缀与 type 不匹配（{eid} vs {dtype}）")

    # 2. 字段对齐
    if dtype in ("system-config", "capability"):
        if "answer" not in fields or not entry.get("answer"):
            score -= 40
            reasons.append("缺失 answer 字段")
    elif dtype == "conversation-topic":
        if "conclusion" not in fields or not entry.get("conclusion"):
            score -= 30
            reasons.append("缺失 conclusion 字段")
    elif dtype == "project-state":
        if "summary" not in fields and "answer" not in fields and "conclusion" not in fields:
            score -= 20
            reasons.append("缺失任何内容字段")

    # 3. 内容长度（key 太短 = 低信号）
    key = entry.get("key", "")
    if len(key) < 10:
        score -= 30
        reasons.append(f"key 过短（{len(key)} 字）")
    elif len(key) < 30:
        score -= 10
        reasons.append(f"key 偏短（{len(key)} 字）")

    # 4. 时间近度（updated 越久远权重越低）
    updated = entry.get("updated", "")
    if updated:
        try:
            updated_dt = datetime.strptime(updated, "%Y-%m-%d").replace(tzinfo=CST)
            days_old = (NOW - updated_dt).days
            if days_old > 90:
                score -= 20
                reasons.append(f"超 90 天未更新（{days_old} 天）")
            elif days_old > 60:
                score -= 10
                reasons.append(f"超 60 天未更新（{days_old} 天）")
        except ValueError:
            score -= 15
            reasons.append("updated 格式异常")

    # 5. type 加权：system-config/project-state 长期有效
    if dtype in ("system-config", "project-state") and score >= 50:
        score += 5  # 兜底保护

    return max(0, score), reasons


def main():
    parser = argparse.ArgumentParser(description="shared-knowledge.json 信噪比清理")
    parser.add_argument("--apply", action="store_true", help="实际归档（默认 dry-run）")
    parser.add_argument("--threshold", type=int, default=30, help="归档阈值（默认 30）")
    args = parser.parse_args()

    if not SK_PATH.exists():
        log(f"❌ {SK_PATH} 不存在")
        sys.exit(1)

    # 备份原文件（apply 前）
    if args.apply:
        backup = SK_PATH.with_suffix(f".json.bak.{NOW.strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(SK_PATH, backup)
        log(f"📦 备份 → {backup}")

    data = json.loads(SK_PATH.read_text())
    entries = data.get("entries", [])
    log(f"📊 原始条目: {len(entries)}")

    scored = []
    for e in entries:
        s, reasons = score_entry(e)
        scored.append((s, reasons, e))

    # 分类
    keep = [e for s, _, e in scored if s >= args.threshold]
    archive = [(e, s, r) for s, r, e in scored if s < args.threshold]
    log(f"✅ 保留: {len(keep)} (score >= {args.threshold})")
    log(f"📦 待归档: {len(archive)} (score < {args.threshold})")

    # 类型分布报告
    from collections import Counter
    type_dist = Counter(e.get("type", "?") for e in entries)
    log(f"📈 类型分布: {dict(type_dist)}")

    archive_type_dist = Counter(e.get("type", "?") for e, _, _ in archive)
    log(f"📦 归档类型分布: {dict(archive_type_dist)}")

    # 归档原因 TOP 5
    all_reasons = []
    for _, reasons, _ in scored:
        all_reasons.extend(reasons)
    reason_dist = Counter(all_reasons)
    log(f"📋 失分原因 TOP 5:")
    for reason, cnt in reason_dist.most_common(5):
        log(f"   {cnt}× {reason}")

    # dry-run vs apply
    if not args.apply:
        log("⚠️ DRY-RUN 模式：未做任何修改。--apply 实际归档")
        log("   归档样本（前 3 条）:")
        for e, s, r in archive[:3]:
            log(f"   - score={s} | type={e.get('type')} | key={e.get('key','')[:50]}")
            log(f"     失分: {'; '.join(r)}")
        return

    # apply：写 archive + 写新主文件
    archive_entries = [e for e, _, _ in archive]
    if ARCHIVE_PATH.exists():
        archive_data = json.loads(ARCHIVE_PATH.read_text())
        archive_data["entries"].extend(archive_entries)
        archive_data["updated"] = NOW.strftime("%Y-%m-%d")
    else:
        archive_data = {
            "version": "1.0-archive",
            "description": "shared-knowledge 历史归档（低分条目，仅供查阅）",
            "created": NOW.strftime("%Y-%m-%d"),
            "entries": archive_entries,
        }
    ARCHIVE_PATH.write_text(json.dumps(archive_data, ensure_ascii=False, indent=2))
    log(f"📦 归档写入: {ARCHIVE_PATH}（共 {len(archive_data['entries'])} 条）")

    # 写回主文件（仅保留高分条目）
    new_data = {
        **data,
        "updated": NOW.strftime("%Y-%m-%d"),
        "entries": keep,
    }
    SK_PATH.write_text(json.dumps(new_data, ensure_ascii=False, indent=2))
    log(f"✅ 主文件更新: {SK_PATH}（保留 {len(keep)} 条）")

    # 写日志
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"sn-cleanup-{NOW.strftime('%Y-%m-%d')}.log"
    with log_file.open("a") as f:
        f.write(f"\n=== {NOW.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.write(f"原始: {len(entries)} | 保留: {len(keep)} | 归档: {len(archive_entries)}\n")
        f.write(f"归档类型: {dict(archive_type_dist)}\n")
        f.write(f"失分 TOP 5: {dict(reason_dist.most_common(5))}\n")
    log(f"📝 日志写入: {log_file}")


if __name__ == "__main__":
    main()
