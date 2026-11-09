#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Unified Memory Search (unified-memory-search.py)
统一的记忆搜索封装脚本 — 双通道并行查询 + 合并排序 + 去重

通道：
  1. memorySearch: OpenClaw 内置语义向量搜索（memory/*.md）
  2. shared-knowledge: tacit-knowledge-catcher 隐性知识库（shared-knowledge.json）

用法：
  python3 unified-memory-search.py "项目部署记录查询"
  python3 unified-memory-search.py --mode catch --input "对话文本"
  python3 unified-memory-search.py --mode stats
  python3 unified-memory-search.py --mode boost --query "跨通道知识断裂" --key "跨通道知识断裂" --type "conversation-topic" --content "核心问题：三层断裂..."

  # 新增：通道 + 日期过滤（修复「各通道问昨日会话」找不到的痛点）
  python3 unified-memory-search.py "昨天聊了啥" --channel telegram --date 2026-06-07
  python3 unified-memory-search.py "微信对话" --channel openclaw-weixin
  python3 unified-memory-search.py "飞书" --channel feishu --date 2026-06-07 --top 20
"""

import json
import re
from datetime import datetime, timezone
import sys
import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
WORKSPACE = Path.home() / ".openclaw/workspace"
SK_PATH = WORKSPACE / "shared-knowledge.json"
MEMORY_DIR = WORKSPACE / "memory"
CONV_DIR = WORKSPACE / "conversations" / "raw"

# 通道别名映射（用户/脚本可能用不同名字）
CHANNEL_ALIASES = {
    "telegram": "telegram",
    "tg": "telegram",
    "feishu": "feishu",
    "fs": "feishu",
    "lark": "feishu",
    "wechat": "openclaw-weixin",
    "微信": "openclaw-weixin",
    "wx": "openclaw-weixin",
    "openclaw-weixin": "openclaw-weixin",
    "qq": "qqbot",
    "qqbot": "qqbot",
    "whatsapp": "whatsapp",
    "wa": "whatsapp",
    "main": "main",  # 无通道标识的兜底
}

# 用户认知的"日切换点"：凌晨 4:00 cron 跑完"会话记忆清理"为界
# 4:00 之前发生的对话属于"逻辑昨天"，4:00 之后属于"逻辑今天"
# 用户认知的"昨天" = (昨天 04:00, 今天 04:00) 24 小时窗口（逻辑日切换点）
LOGICAL_DAY_CUTOFF_HOUR = 4


def resolve_yesterday_window(now: datetime = None) -> tuple[datetime, datetime]:
    """
    计算"昨天"的 24 小时窗口。
    规则: [今天-1天 04:00, 今天 04:00)
    例: 现在是 2026-06-25 09:00 → 窗口 [2026-06-24 04:00, 2026-06-25 04:00)
    例: 现在是 2026-06-25 03:30 → 窗口 [2026-06-23 04:00, 2026-06-24 04:00)
    """
    if now is None:
        now = datetime.now(CST)
    today_4am = now.replace(hour=LOGICAL_DAY_CUTOFF_HOUR, minute=0, second=0, microsecond=0)
    yesterday_4am = today_4am - timedelta(days=1)
    return (yesterday_4am, today_4am)


def parse_dt_arg(s: str) -> datetime:
    """解析 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM' 格式。"""
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=CST) if dt.tzinfo is None else dt
        except ValueError:
            continue
    raise ValueError(f"无法解析时间: {s!r} (支持 YYYY-MM-DD 或 YYYY-MM-DD HH:MM)")

def normalize_channel(c):
    """标准化通道名。None / '' / 'all' 返回 None（不过滤）。"""
    if c is None:
        return None
    c = c.strip().lower()
    if not c or c in ("all", "any", "*"):
        return None
    return CHANNEL_ALIASES.get(c, c)


def parse_l4_filename(filename):
    """
    解析 L4 文件名: 2026-06-07_00-05_agent_main_telegram_direct_1234567890.jsonl
    返回 {date, time, channel, user_id} 字典。
    """
    stem = Path(filename).stem
    parts = stem.split("_")
    result = {"date": None, "time": None, "channel": None, "user_id": None}
    if len(parts) >= 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
        result["date"] = parts[0]
        result["time"] = parts[1]
    try:
        agent_idx = parts.index("main")
        if agent_idx + 1 < len(parts) and parts[agent_idx + 1] != "direct":
            result["channel"] = parts[agent_idx + 1]
        elif agent_idx + 1 < len(parts) and parts[agent_idx + 1] == "direct":
            result["channel"] = "main"
        if agent_idx + 2 < len(parts) and parts[agent_idx + 1] == "direct":
            result["user_id"] = parts[agent_idx + 2]
    except ValueError:
        pass
    return result

# ============================================================
# Core: Shared-Knowledge Search (local, no API needed)
# ============================================================

def load_sk():
    if SK_PATH.exists():
        return json.loads(SK_PATH.read_text())
    return {"version": "1.0", "description": "跨通道共享知识库", "updated": NOW.strftime("%Y-%m-%d"), "entries": []}


def save_sk(data):
    data["updated"] = NOW.strftime("%Y-%m-%d")
    SK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def search_sk(query: str, top_n: int = 10) -> list[dict]:
    """
    Search shared-knowledge.json with keyword matching.
    Returns scored entries.
    """
    sk = load_sk()
    entries = sk.get("entries", [])
    if not entries:
        return []

    query_lower = query.lower()
    chinese_chars = set(re.findall(r'[\u4e00-\u9fff]', query_lower))
    english_words = set(re.findall(r'[a-z0-9]+', query_lower))

    scored = []
    for e in entries:
        # Build searchable text from all string fields
        text = " ".join(v for v in e.values() if isinstance(v, str)).lower()
        key_lower = e.get("key", "").lower()

        # Scoring
        char_matches = sum(1 for c in chinese_chars if c in text)
        word_matches = sum(1 for w in english_words if w in text)
        key_exact = 3 if query_lower in key_lower else 0
        # Bonus: key contains significant overlap
        key_chars = sum(1 for c in chinese_chars if c in key_lower)
        key_words = sum(1 for w in english_words if w in key_lower)

        total = char_matches + word_matches + key_exact + key_chars + key_words
        if total > 0:
            scored.append({
                "score": total,
                "source": "shared-knowledge",
                "type": e.get("type", "unknown"),
                "key": e.get("key", ""),
                "answer": e.get("answer", ""),
                "conclusion": e.get("conclusion", ""),
                "summary": e.get("summary", ""),
                "updated": e.get("updated", ""),
                "source_origin": e.get("source", ""),
                "entry": e,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


# ============================================================
# Core: Memory File Local Search (grep-like, covers memory/ + archive/)
# ============================================================

def search_memory_files(query: str, top_n: int = 10, since_date: str = None, until_date: str = None) -> list[dict]:
    """
    Search memory/*.md and memory/archive/*.md files using keyword matching.
    This provides a local fallback when memorySearch tool is not available.

    Args:
        query: 搜索关键词
        top_n: 返回前 N 条
        since_date: 文件名日期下限（YYYY-MM-DD，包含）
        until_date: 文件名日期上限（YYYY-MM-DD，包含）
    """
    results = []
    query_lower = query.lower()
    chinese_chars = set(re.findall(r'[\u4e00-\u9fff]', query_lower))
    english_words = set(re.findall(r'[a-z0-9]+', query_lower))

    # Search current memory files
    search_dirs = [
        MEMORY_DIR,
        MEMORY_DIR / "archive",
    ]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for md_file in sorted(search_dir.glob("*.md"), reverse=True):
            # 文件名日期过滤（适用于 YYYY-MM-DD.md 格式）
            stem = md_file.stem
            if re.match(r"^\d{4}-\d{2}-\d{2}$", stem):
                if since_date and stem < since_date:
                    continue
                if until_date and stem > until_date:
                    continue
            try:
                content = md_file.read_text(encoding="utf-8")
                lines = content.split("\n")
            except Exception:
                continue

            content_lower = content.lower()

            # Score: count matching chars/words in content
            char_matches = sum(1 for c in chinese_chars if c in content_lower)
            word_matches = sum(1 for w in english_words if w in content_lower)

            if char_matches + word_matches == 0:
                continue

            # Find best matching line (highest density)
            best_line = ""
            best_line_score = 0
            for line in lines:
                line_lower = line.lower()
                line_chars = sum(1 for c in chinese_chars if c in line_lower)
                line_words = sum(1 for w in english_words if w in line_lower)
                line_score = line_chars + line_words
                if line_score > best_line_score:
                    best_line_score = line_score
                    best_line = line.strip()

            # Extract context: find first matching paragraph
            context = _extract_context(lines, query_lower, chinese_chars, english_words)

            results.append({
                "score": char_matches + word_matches,
                "source": "memory-files",
                "file": str(md_file.relative_to(WORKSPACE)),
                "type": "daily-log",
                "key": best_line[:120] if best_line else md_file.stem,
                "answer": context,
                "conclusion": "",
                "summary": "",
                "updated": md_file.stem,  # date from filename
                "source_origin": md_file.stem,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def _extract_context(lines, query_lower, chinese_chars, english_words, context_lines=5):
    """Extract surrounding context from the best matching paragraph."""
    best_start = -1
    best_density = 0

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if not line.strip():
            continue
        score = sum(1 for c in chinese_chars if c in line_lower) + \
                 sum(1 for w in english_words if w in line_lower)
        if score > 0 and score > best_density:
            best_density = score
            best_start = i

    if best_start < 0:
        return ""

    start = max(0, best_start - 2)
    end = min(len(lines), best_start + context_lines)
    context = "\n".join(lines[start:end]).strip()
    return context[:500]


# ============================================================
# Core: Unified Search + Merge + Deduplicate
# ============================================================

def search_session_transcripts(query: str, top_n: int = 5, channel: str = None, date: str = None,
                                since_dt: datetime = None, until_dt: datetime = None) -> list[dict]:
    """
    Third channel: search raw conversation JSONL files.
    Covers conversations/raw/YYYY-MM/ for session transcript keyword search.

    Args:
        query: 搜索关键词
        top_n: 返回前 N 条
        channel: 通道过滤（telegram/feishu/openclaw-weixin/qqbot/whatsapp/main 等，支持别名）
        date: 日期过滤（YYYY-MM-DD 格式，单日）
        since_dt: 时间窗起点（CST，datetime 类型）。与 msg.ts 比较做精确过滤。
        until_dt: 时间窗终点（CST，datetime 类型）。与 msg.ts 比较做精确过滤。

    Returns:
        每条 result 额外带 channel_in_file / date_in_file / msg_channel / msg_role / msg_ts
    """
    results = []
    query_lower = query.lower()
    chinese_chars = set(re.findall(r'[\u4e00-\u9fff]', query_lower))
    english_words = set(re.findall(r'[a-z0-9]+', query_lower))
    ch_filter = normalize_channel(channel)
    date_filter = date  # YYYY-MM-DD 格式

    if not CONV_DIR.exists():
        return results

    # Search recent month dirs（按 date 过滤时只搜该月）
    if date_filter:
        year_month = date_filter[:7]
        month_dirs = [CONV_DIR / year_month]
    elif since_dt or until_dt:
        # 时间窗过滤：搜时间窗涉及的月份（最多 2 个月）
        months = set()
        for dt in (since_dt, until_dt):
            if dt:
                months.add(dt.strftime("%Y-%m"))
        month_dirs = [CONV_DIR / m for m in sorted(months)]
    else:
        month_dirs = sorted(CONV_DIR.glob("*"), reverse=True)[:3]

    for month_dir in month_dirs:
        if not month_dir.exists():
            continue
        # 收集本月所有 jsonl，按 mtime 倒序
        all_files = sorted(month_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        # 关键：先按文件名 channel/date 预过滤
        candidate_files = []
        for f in all_files:
            meta = parse_l4_filename(f.name)
            if date_filter and meta["date"] != date_filter:
                continue
            if ch_filter and meta["channel"] != ch_filter:
                if not (ch_filter == "main" and meta["channel"] is None):
                    continue
            candidate_files.append(f)
        for jsonl_file in candidate_files[:20]:
            try:
                lines = jsonl_file.read_text(encoding="utf-8").strip().split("\n")
            except:
                continue

            file_meta = parse_l4_filename(jsonl_file.name)

            best_msg_score = 0
            best_msg_text = ""
            best_msg_channel = None
            best_msg_role = None
            best_msg_ts = None
            for line in lines:
                try:
                    msg = json.loads(line)
                except:
                    continue

                # 时间窗精确过滤（基于 msg.ts）
                if since_dt or until_dt:
                    msg_ts = msg.get("ts")
                    if msg_ts:
                        try:
                            msg_dt = datetime.fromisoformat(msg_ts)
                            if msg_dt.tzinfo is None:
                                msg_dt = msg_dt.replace(tzinfo=CST)
                        except (ValueError, TypeError):
                            msg_dt = None
                        if msg_dt:
                            if since_dt and msg_dt < since_dt:
                                continue
                            if until_dt and msg_dt >= until_dt:
                                continue
                    # ts 缺失时不过滤（保留，可能 ts 缺失的也是凌晨前对话）

                content = msg.get("content", "")
                if isinstance(content, list):
                    text = " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
                elif isinstance(content, str):
                    text = content
                else:
                    continue

                text_lower = text.lower()
                char_hits = sum(1 for c in chinese_chars if c in text_lower)
                word_hits = sum(1 for w in english_words if w in text_lower)
                score = char_hits + word_hits

                if score > best_msg_score:
                    best_msg_score = score
                    best_msg_channel = msg.get("channel")
                    best_msg_role = msg.get("role")
                    best_msg_ts = msg.get("ts")
                    best_msg_text = text[:300]

            if best_msg_score > 0:
                results.append({
                    "score": best_msg_score,
                    "source": "session-transcripts",
                    "file": str(jsonl_file.relative_to(WORKSPACE)),
                    "type": "transcript",
                    "key": best_msg_text[:120],
                    "answer": best_msg_text,
                    "conclusion": "",
                    "summary": "",
                    "updated": jsonl_file.stem,
                    "source_origin": str(jsonl_file),
                    "channel_in_file": file_meta["channel"],
                    "date_in_file": file_meta["date"],
                    "msg_channel": best_msg_channel,
                    "msg_role": best_msg_role,
                    "msg_ts": best_msg_ts,
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def unified_search(query: str, top_n: int = 10, verbose: bool = False, channel: str = None, date: str = None,
                   since_dt: datetime = None, until_dt: datetime = None, since_date: str = None, until_date: str = None) -> list[dict]:
    """
    Unified search: queries all channels (3-channel), merges, deduplicates, and ranks.
    Channels: 1) shared-knowledge 2) memory-files 3) session-transcripts
    Returns top results from best channel first.

    Args:
        channel: 通道过滤（透传到 search_session_transcripts；同时对 L4 命中加权）
        date: 日期过滤（透传到 search_session_transcripts；与时间窗互斥）
        since_dt: 时间窗起点（CST，datetime，msg.ts 精确过滤）
        until_dt: 时间窗终点（CST，datetime，msg.ts 精确过滤）
        since_date: daily log 文件名日期下限（YYYY-MM-DD）
        until_date: daily log 文件名日期上限（YYYY-MM-DD）

    增强（2026-06-08）：当指定 channel/date 时，L4 (session-transcripts) 命中 +1.5x 加权，
    避免被 L6 缓存（跨通道知识）淹没——L4 才是通道隔离的真理源。
    增强（2026-06-25）：--yesterday 模式：自动解析为 (昨天 04:00, 今天 04:00) 时间窗。
    """
    # Run all three channels
    sk_results = search_sk(query, top_n=20)
    mf_results = search_memory_files(query, top_n=20, since_date=since_date, until_date=until_date)
    st_results = search_session_transcripts(query, top_n=5, channel=channel, date=date,
                                              since_dt=since_dt, until_dt=until_dt)

    # 通道加权：当指定 channel/date 时，L4 命中加分（因为 L4 才是通道隔离的真理源）
    has_channel_filter = bool(normalize_channel(channel) or date)
    if has_channel_filter:
        for r in st_results:
            r["score"] = int(r["score"] * 1.5) + 2
        for r in sk_results:
            r["channel_isolated"] = False
        for r in mf_results:
            r["channel_isolated"] = False
        for r in st_results:
            r["channel_isolated"] = True
        # v2.1 时间近度加权（多轮实战时间近度加权调优反馈
        # 旧 session-analysis 被 channel_isolated 推到首位——近度不加权就排不对）
        # 近 7 天 +5 / 30 天 +2 / 更早 +0
        time_now = datetime.now(timezone.utc)
        for r in st_results:
            msg_ts_str = r.get("msg_ts", "")
            if not msg_ts_str:
                continue
            try:
                msg_ts = datetime.fromisoformat(msg_ts_str.replace("Z", "+00:00"))
                age_days = (time_now - msg_ts).days
                if age_days <= 7:
                    time_bonus = 5
                elif age_days <= 30:
                    time_bonus = 2
                else:
                    time_bonus = 0
                r["score"] += time_bonus
            except (ValueError, TypeError):
                continue
    else:
        for r in sk_results + mf_results + st_results:
            r["channel_isolated"] = True

    # Tag each result with channel
    all_results = []
    for r in sk_results:
        r["channel"] = "shared-knowledge"
        all_results.append(r)
    for r in mf_results:
        r["channel"] = "memory-files"
        all_results.append(r)
    for r in st_results:
        r["channel"] = "session-transcripts"
        all_results.append(r)

    # Deduplicate: if two results from different channels have similar content,
    # keep the higher-scored one
    deduped = []
    seen_keys = set()

    for r in all_results:
        content = (r.get("answer", "") or r.get("conclusion", "") or r.get("summary", ""))[:50]
        if content and content in seen_keys:
            continue
        if content:
            seen_keys.add(content)
        file_key = f"{r.get('file', '')}:{r.get('key', '')[:30]}"
        if file_key in seen_keys:
            continue
        seen_keys.add(file_key)
        deduped.append(r)

    # Re-sort：指定 channel/date 时，channel_isolated=True 的排前面（避免被跨通道 L6 淹没）
    def sort_key(x):
        isolated_bonus = 1000 if x.get("channel_isolated") else 0
        return isolated_bonus + x["score"]
    deduped.sort(key=sort_key, reverse=True)
    return deduped[:top_n]


def format_results(results: list[dict], query: str) -> str:
    """Format search results for human-readable output."""
    if not results:
        return f"⚠️ 未找到与「{query}」相关的记忆"

    lines = [f"🔍 统一记忆搜索：「{query}」\n"]
    lines.append(f"找到 {len(results)} 条结果（双通道合并去重）\n")

    channels = {}
    for r in results:
        ch = r["channel"]
        channels[ch] = channels.get(ch, 0) + 1

    channel_summary = " | ".join(f"{ch}: {n}条" for ch, n in channels.items())
    lines.append(f"通道分布：{channel_summary}\n")
    lines.append("─" * 60)

    for i, r in enumerate(results, 1):
        ch_icon = {"shared-knowledge": "💡", "memory-files": "📝", "session-transcripts": "💬"}.get(r["channel"], "❓")
        lines.append(f"\n{i}. {ch_icon} [{r['channel']}] [{r.get('type', '?')}]")
        lines.append(f"   📌 {r['key'][:120]}")

        # Show answer/conclusion/context
        answer = r.get("answer", "") or r.get("conclusion", "") or ""
        if answer:
            # Truncate to readable length
            if len(answer) > 200:
                answer = answer[:200] + "..."
            lines.append(f"   → {answer}")

        # Show source
        source = r.get("file", r.get("source_origin", ""))
        updated = r.get("updated", "")
        if source or updated:
            lines.append(f"   📁 {source} | 更新: {updated}")

    return "\n".join(lines)


# ============================================================
# Boost: Add missing knowledge to shared-knowledge
# ============================================================

def detect_type(text: str) -> str | None:
    """Detect conversation content type for auto-catch."""
    text_lower = text.lower()

    if any(k in text_lower for k in ["保存在哪", "路径是", "配置在哪", "位置在哪", "存在哪个文件", "在哪", "index在哪"]):
        return "system-config"
    if any(k in text_lower for k in ["你能做什么", "助手能干什么", "有什么限制", "不能做什么"]):
        return "capability"
    if any(k in text_lower for k in ["项目现在", "做到哪了", "phase", "进度", "阶段", "项目进度"]):
        return "project-state"
    if any(k in text_lower for k in [
        "我们讨论过", "我们聊过", "我们谈过", "之前聊", "之前讨论",
        "之前说过", "昨天聊", "上次聊", "之前是怎么做的",
        "我有没有告诉过你", "结论是什么", "最终决定", "所以",
        "上次说的", "之前我们", "不是说过",
        # 修复（2026-06-22 同步自 tacit-knowledge-catcher）：拍板/决策式触发识别
        "就按", "就这", "就这么", "就这个", "拍板", "全部搞",
        "开干", "就这么定了", "就这么办", "就这么干", "就这么定",
        "用这个", "按这个来", "按这个推进", "强观点",
        "我的判断", "动手", "结论：",
    ]):
        return "conversation-topic"
    return None


def boost_to_sk(query: str, key: str, dtype: str, content: str) -> bool:
    """
    Manually boost a search result into shared-knowledge for better future recall.
    This is the "close the loop" step after a search miss.
    """
    sk = load_sk()
    entries = sk.get("entries", [])

    # Check if similar key already exists
    existing_idx = None
    for i, e in enumerate(entries):
        if e.get("key", "") == key or (key in e.get("key", "") and len(key) > 5):
            existing_idx = i
            break

    entry = {
        "id": f"{dtype[:3]}-{hashlib.md5(f'{key}{NOW.isoformat()}'.encode()).hexdigest()[:8]}",
        "type": dtype,
        "key": key,
        "updated": NOW.strftime("%Y-%m-%d"),
        "source": "unified-search-boost",
    }

    if dtype in ("system-config", "capability", "project-state"):
        entry["answer"] = content[:500]
    elif dtype == "conversation-topic":
        entry["summary"] = content[:300]
        entry["conclusion"] = content[:500]
        entry["date"] = NOW.strftime("%Y-%m-%d")

    if existing_idx is not None:
        sk["entries"][existing_idx] = entry
        action = "updated"
    else:
        sk["entries"].append(entry)
        action = "added"

    save_sk(sk)
    return action


def auto_catch(text: str, source: str = "unified-auto") -> list[dict]:
    """
    Auto-detect and catch tacit knowledge from conversation text.
    Enhanced version with more trigger patterns.
    """
    dtype = detect_type(text)
    if not dtype:
        return []

    # Extract key from text
    lines = text.strip().split("\n")
    key = lines[0].strip().strip("#*").strip()[:120]

    # If key is too long or generic, try to find a better one
    if len(key) > 100 or len(key) < 3:
        for line in lines:
            for trigger in ["结论", "决定", "所以", "配置", "路径", "位置"]:
                if trigger in line:
                    key = line.strip().strip("#*").strip()[:120]
                    break
            if 3 < len(key) <= 100:
                break

    sk = load_sk()
    existing = [i for i, e in enumerate(sk["entries"]) if e.get("key") == key]

    entry = {
        "id": f"{dtype[:3]}-{hashlib.md5(f'{key}{NOW.isoformat()}'.encode()).hexdigest()[:8]}",
        "type": dtype,
        "key": key,
        "updated": NOW.strftime("%Y-%m-%d"),
        "source": source,
    }

    if dtype in ("system-config", "capability", "project-state"):
        entry["answer"] = text[:500]
    elif dtype == "conversation-topic":
        entry["summary"] = text[:300]
        entry["conclusion"] = text[:500]
        entry["date"] = NOW.strftime("%Y-%m-%d")

    if existing:
        sk["entries"][existing[0]].update(entry)
    else:
        sk["entries"].append(entry)

    save_sk(sk)
    return [entry]


# ============================================================
# Stats
# ============================================================

def print_stats():
    """Print memory system statistics."""
    sk = load_sk()
    entries = sk.get("entries", [])

    # Count by type
    type_counts = {}
    for e in entries:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Count memory files
    current_logs = list(MEMORY_DIR.glob("*.md")) if MEMORY_DIR.exists() else []
    archive_logs = list((MEMORY_DIR / "archive").glob("*.md")) if (MEMORY_DIR / "archive").exists() else []

    print("📊 记忆系统统计")
    print("=" * 50)
    print(f"shared-knowledge: {len(entries)} 条")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  - {t}: {c}")
    print(f"memory/ 日志: {len(current_logs)} 份（当前）")
    print(f"memory/archive/: {len(archive_logs)} 份（归档）")
    print(f"总计可搜索文件: {len(current_logs) + len(archive_logs)} 份")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Unified Memory Search — 双通道统一记忆搜索")
    parser.add_argument("query", nargs="?", help="搜索查询")
    parser.add_argument("--mode", choices=["search", "catch", "boost", "stats"], default="search")
    parser.add_argument("--input", help="对话文本（catch 模式）")
    parser.add_argument("--key", help="知识条目 key（boost 模式）")
    parser.add_argument("--type", help="知识类型（boost 模式：system-config/capability/project-state/conversation-topic）")
    parser.add_argument("--content", help="知识内容（boost 模式）")
    parser.add_argument("--top", type=int, default=10, help="返回结果数（默认10）")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--source", default="unified-auto", help="来源标记")
    parser.add_argument("--channel", help="通道过滤（telegram/feishu/openclaw-weixin/qqbot/whatsapp/main，支持别名 wx/tg/fs/微信）")
    parser.add_argument("--date", help="日期过滤（YYYY-MM-DD 格式，与 --yesterday/--since/--until 互斥）")
    # 「昨天」语义窗口 = (昨天 04:00, 今天 04:00) 24 小时
    parser.add_argument("--yesterday", action="store_true", help="「昨天」语义窗口 = (昨天 04:00, 今天 04:00)。与 --date 互斥。")
    parser.add_argument("--since", help="时间窗起点 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM'（CST）。仅作用于 L4 session-transcripts 精确时间过滤。")
    parser.add_argument("--until", help="时间窗终点 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM'（CST）。仅作用于 L4 session-transcripts 精确时间过滤。")

    args = parser.parse_args()

    if args.mode == "stats":
        print_stats()

    elif args.mode == "catch":
        if not args.input:
            print("❌ --input required")
            sys.exit(1)
        results = auto_catch(args.input, args.source)
        if results:
            print(f"✅ 捕捉 {len(results)} 条隐性知识:")
            for r in results:
                print(f"  [{r['type']}] {r['key'][:80]}")
        else:
            print("⚠️ 未检测到隐性知识（无匹配触发词）")

    elif args.mode == "boost":
        if not args.key or not args.type or not args.content:
            print("❌ --key, --type, --content required for boost mode")
            sys.exit(1)
        action = boost_to_sk(args.query or args.key, args.key, args.type, args.content)
        print(f"✅ 知识库已{action}: [{args.type}] {args.key[:60]}")

    elif args.mode == "search":
        if not args.query:
            print("❌ 请提供搜索查询")
            sys.exit(1)
        ch = normalize_channel(args.channel)
        if args.channel and not ch:
            print(f"⚠️ --channel '{args.channel}' 被识别为 'all'，不过滤")
        # 互斥检查
        if args.yesterday and args.date:
            print("❌ --yesterday 与 --date 互斥，只能用其中一个")
            sys.exit(1)
        # 解析时间窗
        since_dt = None
        until_dt = None
        since_date = None
        until_date = None
        if args.yesterday:
            since_dt, until_dt = resolve_yesterday_window()
            # L3 daily log 文件名是按"逻辑日 04:00 切"，所以"昨天"对应的 L3 文件 = 昨天 + 今天的 daily log
            today_date = NOW.strftime("%Y-%m-%d")
            yesterday_date = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")
            # 窗口起点是昨天 04:00 = 昨天 daily log；终点是今天 04:00 = 不会超过今天 daily log
            since_date = yesterday_date
            until_date = today_date
        else:
            if args.since:
                try:
                    since_dt = parse_dt_arg(args.since)
                except ValueError as e:
                    print(f"❌ {e}")
                    sys.exit(1)
                # daily log 文件名取 since 的日期
                since_date = since_dt.strftime("%Y-%m-%d")
            if args.until:
                try:
                    until_dt = parse_dt_arg(args.until)
                except ValueError as e:
                    print(f"❌ {e}")
                    sys.exit(1)
                # 包含直到日期的 daily log
                until_date = until_dt.strftime("%Y-%m-%d")
        # 过滤条件提示：只在非 JSON 模式打印，避免污染 JSON 输出
        if not args.json and (ch or args.date or args.yesterday or since_dt or until_dt):
            time_window = f"[{since_dt.strftime('%Y-%m-%d %H:%M') if since_dt else '—'}, {until_dt.strftime('%Y-%m-%d %H:%M') if until_dt else '—'})" if (since_dt or until_dt) else None
            print(f"🔍 过滤条件: channel={ch!r}, date={args.date!r}, yesterday={args.yesterday}, time_window={time_window}, daily_log_range=[{since_date}, {until_date}]")
        results = unified_search(args.query, top_n=args.top, channel=ch, date=args.date,
                                  since_dt=since_dt, until_dt=until_dt,
                                  since_date=since_date, until_date=until_date)
        if args.json:
            # Strip internal fields for clean output
            clean = []
            for r in results:
                clean.append({
                    "channel": r["channel"],
                    "type": r.get("type", ""),
                    "key": r["key"],
                    "content": r.get("answer", "") or r.get("conclusion", ""),
                    "source": r.get("file", ""),
                    "updated": r.get("updated", ""),
                    "score": r["score"],
                    "channel_in_file": r.get("channel_in_file"),
                    "date_in_file": r.get("date_in_file"),
                    "msg_channel": r.get("msg_channel"),
                    "msg_role": r.get("msg_role"),
                    "msg_ts": r.get("msg_ts"),
                })
            print(json.dumps(clean, ensure_ascii=False, indent=2))
        else:
            print(format_results(results, args.query))
