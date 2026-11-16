#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""保存会话记录 — 直接读 session JSONL 文件，不依赖 LLM

开源脱敏版（2026-11-16 自生产 v5 回填）：不含任何真实定时任务 ID / 账号 ID /
人名 / 机器特定路径；路径均基于 Path.home() 的 OpenClaw 标准安装约定。

v2 改造 (2026-06-08): 增量追加模式
- 文件名从 YYYY-MM-DD_HH-MM_<key>.jsonl 改成 YYYY-MM-DD_<key>.jsonl（一天一个）
- 新增 .state.json 记录每个 session 的 last_saved_ts，下次只追加 ts > state 的消息
- atomic write state（tmp + rename）防止闪断时 state 半写
- state 更新时机：append 写完文件后**才**更新 state（闪断保护——极端情况会重复几条，
  但下游 unified-memory-search.py 按 (role, content[:200]) 去重，重复无影响）
- 旧文件名 YYYY-MM-DD_HH-MM_<key>.jsonl 文件保留不删（向后兼容）
"""

import json, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
HOURS24 = NOW - timedelta(hours=24)
OUT_DIR = Path.home() / ".openclaw/workspace/conversations/raw" / NOW.strftime("%Y-%m")
SKIP_PATTERNS = ["HEARTBEAT.md", "保存会话记录任务触发", "NO_REPLY"]
SKIP_CONTENT_PREFIXES = ["System:"]
STORE = Path.home() / ".openclaw/agents/main/sessions/sessions.json"
STATE_FILE = Path.home() / ".openclaw/workspace/conversations/.state.json"

# v5 (2026-10-25 心跳修复): 本脚本每次运行会为「无 .jsonl 的 session」物化一份
# oc-tx-<sid>.jsonl 到 TMPDIR，但从不清理 → 实测累积数千个文件 / 数百 MB。
# 记录本轮生成的临时文件，脚本结束时统一删除；同时清扫历史遗留（>24h）。
_TMP_OC_TX = []

def extract_text(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return " ".join(t.strip() for t in texts if t.strip())
    return ""

def should_skip(content):
    if not content or not content.strip():
        return True
    for p in SKIP_PATTERNS:
        if p in content:
            return True
    for p in SKIP_CONTENT_PREFIXES:
        if content.strip().startswith(p):
            return True
    return False

def load_state() -> dict:
    """加载 state 文件。损坏/不存在 → 返空 dict（首次跑或损坏后重建）"""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

def save_state(state: dict) -> None:
    """atomic write state：先写 .tmp，rename 覆盖。闪断时 state 不会半写"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(STATE_FILE)

OUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. 加载 sessions index（用于识别 session key 和 updatedAt）
# v3 (2026-09-04): gateway 2026.8.2 将 session 存储迁移到 SQLite，不再生成 sessions.json。
# sessions.json 缺失时，从 openclaw-agent.sqlite（先拷贝到 /tmp 避开 live-state 锁）重建索引。
def rebuild_store_from_sqlite() -> dict:
    import shutil, sqlite3, tempfile, time
    src = Path.home() / ".openclaw/agents/main/agent/openclaw-agent.sqlite"
    tmp = Path(tempfile.gettempdir()) / "oc-agent-index-copy.sqlite"
    # v4 (2026-10-23): 主库已 WAL 模式且体积达 GB 级，单独 copy 主文件会在 gateway
    # 正在 checkpoint 时拷到撕裂副本，报 "database disk image is malformed"。
    # 修复：主库 + -wal + -shm 三件套一起复制，并容忍单次 retry。
    last_err = None
    conn = None
    for attempt in range(3):
        for suffix in ("", "-wal", "-shm"):
            s = Path(str(src) + suffix)
            if s.exists():
                shutil.copy2(s, Path(str(tmp) + suffix))
        try:
            conn = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
            conn.execute("SELECT count(*) FROM session_nodes").fetchone()
            break
        except sqlite3.DatabaseError as exc:
            last_err = exc
            conn = None
            print(f"⚠️ 第 {attempt + 1} 次重建副本不可用（{exc}），重试中…")
            time.sleep(5)
    if conn is None:
        raise last_err
    sess_dir = Path.home() / ".openclaw/agents/main/sessions"
    store = {}
    for key, sid, upd, entry in conn.execute(
        "SELECT session_key, current_session_id, updated_at, entry_json FROM session_nodes"
    ):
        try:
            meta = json.loads(entry) if entry else {}
        except json.JSONDecodeError:
            meta = {}
        meta["updatedAt"] = upd
        sf = sess_dir / f"{sid}.jsonl"
        if sf.exists():
            meta["sessionFile"] = str(sf)
        else:
            # 新架构：transcript 只存在 SQLite 中 → 物化到 /tmp 供读取
            rows = conn.execute(
                "SELECT event_json FROM transcript_events WHERE session_id=? ORDER BY seq",
                (sid,),
            ).fetchall()
            # v5 (2026-10-25 心跳修复): transcript_events 表存在 event_json=NULL 行
            # (实测相当比例的行含 NULL，涉及大量 session)。原代码
            #   "".join(r[0] + "\n" for r in rows)
            # 遇到 NULL 会抛 TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'
            # -> 定时窗口内必失败（失败计数随调度逐轮累积）。
            # 修复: 跳过 NULL 行。语义等价——下游只认 type=="message" 的合法 JSON,
            # NULL 行本就会被 json.loads 跳过。
            payloads = [r[0] for r in rows if r[0] is not None]
            if not payloads:
                continue
            tmpf = Path(tempfile.gettempdir()) / f"oc-tx-{sid}.jsonl"
            tmpf.write_text("".join(p + "\n" for p in payloads))
            _TMP_OC_TX.append(tmpf)   # v5: 记入待清理清单（脚本结尾统一删除）
            meta["sessionFile"] = str(tmpf)
        store[key] = meta
    conn.close()
    tmp.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(str(tmp) + suffix).unlink(missing_ok=True)
    return store

if STORE.exists():
    store = json.loads(STORE.read_text())
else:
    try:
        store = rebuild_store_from_sqlite()
        print(f"ℹ️ sessions.json 不存在（SQLite 迁移），从 openclaw-agent.sqlite 重建 {len(store)} 个会话")
    except Exception as e:
        print(f"❌ sessions.json not found 且 SQLite 重建失败: {e}")
        exit(1)
SESS_DIR = Path.home() / ".openclaw/agents/main/sessions"
state = load_state()
total_saved = 0
total_appended_lines = 0

def find_latest_session_file(key):
    """在 sessions 目录中找到匹配 key 的最新 session 文件。

    优先使用 sessions.json 的 sessionFile 指针。
    如果该文件已冻结（最后修改超过 1 小时前），
    则扫描目录找同 session 的 checkpoint 文件或更新的 .jsonl。
    """
    meta = store.get(key, {})
    session_file = meta.get("sessionFile", "")

    # sessionFile 存在且最近有更新 → 直接用
    if session_file and os.path.exists(session_file):
        mtime = os.path.getmtime(session_file)
        age_hours = (NOW.timestamp() - mtime) / 3600
        if age_hours < 1:
            return session_file

    # sessionFile 冻结或不存在 → 从 sessions.json 提取 session UUID，扫描目录
    # sessionFile 格式: /path/78706bc2-....jsonl → 提取 UUID
    uuid = ""
    if session_file:
        basename = os.path.basename(session_file).replace(".jsonl", "")
        # 也可能是 checkpoint 文件: uuid.checkpoint.xxx.jsonl
        parts = basename.split(".checkpoint.")
        if len(parts) > 0:
            uuid = parts[0]

    candidates = []
    for f in os.listdir(SESS_DIR):
        if not f.endswith(".jsonl") or "trajectory" in f:
            continue
        fpath = os.path.join(SESS_DIR, f)
        # 匹配同 UUID 的文件（包括 checkpoint）
        if uuid and f.startswith(uuid):
            candidates.append(fpath)
        # 也保留非 checkpoint 的 .jsonl（可能 sessionFile 被更新了）
        elif f == os.path.basename(session_file or ""):
            candidates.append(fpath)

    if candidates:
        # 返回最新修改的文件
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    # 兜底：直接用 sessionFile（即使冻结）
    if session_file and os.path.exists(session_file):
        return session_file

    return None

# 2. 遍历所有 session，找 24h 内活跃的 direct chat
for key, meta in store.items():
    kind = meta.get("kind", "")

    # 只处理 direct chat（whatsapp direct / telegram direct）
    if ":cron:" in key or ":subagent:" in key:
        continue
    if kind in ("other", "isolated", "subagent"):
        continue

    updated_at = meta.get("updatedAt", 0)
    cutoff = int(HOURS24.timestamp() * 1000)
    if updated_at < cutoff:
        continue

    session_file = find_latest_session_file(key)
    if not session_file:
        continue

    # 输出文件名（v2：一天一个 session 一个文件，append 模式）
    fname = f"{NOW.strftime('%Y-%m-%d')}_{key.replace(':', '_').replace('/', '_')}.jsonl"
    fpath = OUT_DIR / fname

    # 增量过滤：只取 ts > state[key] 的消息
    last_ts = state.get(key, "")

    # 3. 读取 session JSONL，提取新增消息
    lines = []
    max_ts = last_ts
    try:
        with open(session_file) as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "message":
                    continue

                msg = entry.get("message", {})
                role = msg.get("role", "")
                if role in ("system", "toolResult"):
                    continue

                content = extract_text(msg.get("content", ""))
                if should_skip(content):
                    continue

                ts_raw = msg.get("timestamp", 0)
                if isinstance(ts_raw, (int, float)) and ts_raw > 0:
                    ts_str = datetime.fromtimestamp(ts_raw / 1000, tz=CST).isoformat()
                elif isinstance(ts_raw, str):
                    ts_str = ts_raw
                else:
                    ts_str = NOW.isoformat()

                # v2 增量：跳过已写过的
                if last_ts and ts_str <= last_ts:
                    continue

                channel = meta.get("lastChannel", key.split(":")[2] if len(key.split(":")) > 2 else "")
                lines.append(json.dumps({"ts": ts_str, "role": role, "content": content, "channel": channel}, ensure_ascii=False))
                if ts_str > max_ts:
                    max_ts = ts_str
    except Exception as e:
        print(f"  ❌ {key}: {e}")
        continue

    if lines:
        # append 模式（同文件已存在 → 追加；不存在 → 新建）
        with open(fpath, "a", errors='surrogatepass') as f:
            f.write("\n".join(lines) + "\n")
        # 写完文件后**才**更新 state（闪断保护）
        state[key] = max_ts
        total_saved += 1
        total_appended_lines += len(lines)
        print(f"  ✅ {key}: +{len(lines)} 条 (append, max_ts={max_ts[:19]})")
    else:
        print(f"  ⏭️ {key}: 无新增消息（last_ts={last_ts[:19] if last_ts else '无'})")

# 4. 写 state（atomic）
save_state(state)
print(f"\n✅ 完成，保存 {total_saved} 个会话（共 {total_appended_lines} 条新增）")

# 5. 写 daily log
log_path = Path.home() / ".openclaw/workspace/memory" / (NOW.strftime("%Y-%m-%d") + ".md")
try:
    with open(log_path, "a") as f:
        f.write(f"\n---\n## 会话保存（脚本 v2）{NOW.strftime(' %H:%M')}\n- 追加 {total_saved} 个 direct chat 会话，共 {total_appended_lines} 条\n")
except Exception:
    pass

# 6. 清理本轮 + 历史遗留的 oc-tx-*.jsonl 临时物化文件（v5, 2026-10-25）
#    这些文件只在本脚本运行期间被读取（meta["sessionFile"] 指向它们），
#    运行结束即可安全删除。此前从不清理 → TMPDIR 累积到数百 MB。
try:
    import tempfile as _tf
    _tmpdir = Path(_tf.gettempdir())
    _freed = 0
    _n = 0
    for _f in _TMP_OC_TX:
        try:
            if _f.exists():
                _freed += _f.stat().st_size
                _f.unlink()
                _n += 1
        except OSError:
            pass
    # 清扫历史遗留：24h 前的 oc-tx 文件（无进程持有，可安全删）
    import time as _time
    _cutoff = _time.time() - 86400
    for _f in _tmpdir.glob("oc-tx-*.jsonl"):
        try:
            if _f.stat().st_mtime < _cutoff:
                _freed += _f.stat().st_size
                _f.unlink()
                _n += 1
        except OSError:
            pass
    if _n:
        print(f"🧹 清理 oc-tx 临时文件 {_n} 个，释放 {_freed / 1024 / 1024:.1f} MB")
except Exception as e:
    print(f"⚠️ oc-tx 清理跳过: {e}")
