#!/usr/bin/env python3
"""
Tacit Knowledge Catcher
自动捕捉对话中的隐性知识，写入 shared-knowledge.json

两种模式：
  python3 tacit-knowledge-catcher.py --mode catch --input <对话文本>
  python3 tacit-knowledge-catcher.py --mode inject --query <用户问题>
"""

import json
import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
WORKSPACE = Path.home() / ".openclaw/workspace"
SK_PATH = WORKSPACE / "shared-knowledge.json"
CONV_DIR = WORKSPACE / "conversations/raw"


def load_sk():
    """加载 shared-knowledge.json"""
    if SK_PATH.exists():
        return json.loads(SK_PATH.read_text())
    return {"version": "1.0", "description": "跨通道共享知识库", "updated": NOW.strftime("%Y-%m-%d"), "entries": []}


def save_sk(data):
    """保存 shared-knowledge.json（atomic write：闪断保护）
    
    数据安全：真实数据不能损坏。使用 .tmp + rename 原子模式。
    """
    data["updated"] = NOW.strftime("%Y-%m-%d")
    # atomic write：先写 .tmp 文件，再 rename 到目标文件
    tmp_path = SK_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp_path.replace(SK_PATH)  # 原子替换（同文件系统 rename 是原子的）


def gen_id(key: str) -> str:
    """生成唯一 ID
    
    修复记录：原使用模块级 NOW 导致同 key 同秒生成同一 ID。
    修复：改用函数内 datetime.now(CST)，确保每次调用 timestamp 唯到。
    """
    ts = datetime.now(CST).strftime('%Y%m%d%H%M%S%f')  # 唯到微秒
    h = hashlib.md5(f"{key}{ts}".encode()).hexdigest()[:8]
    return h


def detect_type(text: str) -> str | None:
    """检测对话内容类型"""
    text_lower = text.lower()
    # 2026-06-09 扩展：逐行检查 + 支持 AND 组合（"时间词 + 聊/讨论"）
    lines_to_check = [text_lower] + [l.strip() for l in text_lower.split('\n')]
    full_text = ' '.join(lines_to_check)

    def hit_any(kws: list[str]) -> bool:
        return any(any(k in s for k in kws) for s in lines_to_check)

    def hit_and(group1: list[str], group2: list[str]) -> bool:
        """两词都要出现（不要求相邻）"""
        g1 = any(k in full_text for k in group1)
        g2 = any(k in full_text for k in group2)
        return g1 and g2

    # system-config
    if hit_any(["保存在哪", "路径是", "配置在哪", "位置在哪", "存在哪个文件", "在哪", "index在哪"]):
        return "system-config"
    # capability
    if hit_any(["你能做什么", "助手能干什么", "有什么限制", "不能做什么"]):
        return "capability"
    # project-state
    if hit_any(["项目现在", "做到哪了", "phase", "进度", "阶段", "项目进度"]):
        return "project-state"
    # conversation-topic
    # 包含两类触发：复盘式（回顾性）+ 拍板式（决策性）
    # 原版仅识别复盘式，导致正向决策/共识不触发——旧版根因
    conv_topic_hit = hit_any([
        # 复盘式（原有）
        "我们讨论过", "我们聊过", "我们谈过", "之前聊", "之前讨论",
        "之前说过", "昨天聊", "昨晚聊", "前天聊", "上次聊", "之前是怎么做的",
        "我有没有告诉过你", "结论是什么", "最终决定", "所以",
        # 拍板/决策式（2026-06-09 扩展）
        "就按", "就这", "就这么", "就这个", "拍板", "全部搞", "动手就是",
        "开干", "就这么定了", "就这么办", "就这么干", "就这么定",
        "用这个", "按这个来", "按这个推进", "强观点", "我的建议",
        "我的判断", "动手", "结论：",
    ]) or hit_and(
        # AND 组合：时间词 + 聊/讨论（解决"昨晚最后聊"、"前天讨论"等不连续表达）
        ["昨晚", "昨天", "前天", "上周", "上回", "今早", "前晚"],
        ["聊", "讨论", "谈", "说过"]
    )
    if conv_topic_hit:
        return "conversation-topic"
    return None


def extract_key_and_answer(text: str, dtype: str) -> tuple[str, str]:
    """提取 key 和 answer"""
    lines = text.strip().split("\n")
    
    # system-config: 提取问题+答案
    if dtype == "system-config":
        for line in lines:
            if any(k in line for k in ["在哪", "路径", "位置", "保存"]):
                key = line.strip().strip("#*").strip()
                # 找答案（下一行或同行）
                idx = lines.index(line)
                if idx + 1 < len(lines):
                    answer = lines[idx + 1].strip().strip("#*").strip()
                else:
                    answer = key
                return key[:100], answer[:500]
        return f"system-config-{NOW.strftime('%H%M%S')}", text[:200]
    
    # conversation-topic: 提取话题+结论
    if dtype == "conversation-topic":
        # 结论触发词：复盘式 + 拍板式（2026-06-09 扩展，与 detect_type 一致）
        conclusion_kws = [
            # 复盘式
            "结论", "所以", "最终", "决定",
            # 拍板/决策式
            "拍板", "就按", "就这", "就这么", "就这个", "全部搞", "动手就是",
            "开干", "就这么定了", "就这么办", "就这么干", "就这么定",
            "用这个", "按这个来", "按这个推进", "强观点", "我的建议",
            "我的判断", "动手", "定了", "上", "就这么", "动手",
        ]
        for line in lines:
            if any(k in line for k in conclusion_kws):
                conclusion = line.strip().strip("#*").strip()
                # 往前找话题
                for prev in reversed(lines[:lines.index(line)]):
                    if prev.strip() and not prev.startswith("##"):
                        topic = prev.strip().strip("#*").strip()
                        return topic[:100], conclusion[:500]
                # 2026-06-09 修复：单行场景（无前置话题）→ 同一行既作 key 又作 conclusion
                return conclusion[:100], conclusion[:500]
        # 没有结论，hit_and 触发（“昨晚最后聊”）场景：取整段为 conclusion
        if len(lines) == 1:
            return lines[0][:100], lines[0][:500]
        return lines[0][:100] if lines else "unknown", lines[1][:500] if len(lines) > 1 else ""
    
    return f"topic-{NOW.strftime('%H%M%S')}", text[:200]


def catch(conversation_text: str, source: str = "manual") -> list[dict]:
    """
    catch 模式：分析对话，检测隐性知识，写入 shared-knowledge.json
    返回：写入的条目列表
    """
    dtype = detect_type(conversation_text)
    if not dtype:
        return []
    
    key, answer = extract_key_and_answer(conversation_text, dtype)
    entry_id = f"{dtype[:3]}-{gen_id(key)}"
    
    entry = {
        "id": entry_id,
        "type": dtype,
        "key": key,
        "updated": NOW.strftime("%Y-%m-%d"),
        "source": source,
    }
    
    if dtype in ("system-config", "capability"):
        entry["answer"] = answer
    elif dtype == "conversation-topic":
        entry["summary"] = conversation_text[:300]
        entry["conclusion"] = answer
        entry["date"] = NOW.strftime("%Y-%m-%d")
    
    # 读取现有数据，检查是否已有相同 key
    sk = load_sk()
    existing = [i for i, e in enumerate(sk["entries"]) if e.get("key") == key]
    
    if existing:
        # 更新已有条目
        sk["entries"][existing[0]].update(entry)
    else:
        sk["entries"].append(entry)
    
    save_sk(sk)
    return [entry]


def inject(query: str, top_n: int = 5) -> list[dict]:
    """
    inject 模式：根据 query 从 shared-knowledge 找相关条目
    返回：相关条目列表（按更新时间倒序）
    """
    sk = load_sk()
    entries = sk.get("entries", [])
    
    if not entries:
        return []
    
    # 简单匹配：query 中的每个字符/词是否出现在 entry 的 key/summary/answer 里
    # 支持中文（逐字符）+ 英文（逐词）
    import re
    query_lower = query.lower()
    # 提取中文字符 + 英文单词
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', query_lower)
    english_words = re.findall(r'[a-z0-9]+', query_lower)
    
    scored = []
    for e in entries:
        text = " ".join(v for v in e.values() if isinstance(v, str)).lower()
        # 中文字符匹配（至少1个）
        char_matches = sum(1 for c in chinese_chars if c in text)
        # 英文单词匹配
        word_matches = sum(1 for w in english_words if w in text)
        # key 完全包含
        key_match = 1 if query_lower in e.get("key", "").lower() else 0
        total = char_matches + word_matches + key_match * 2
        if total > 0:
            scored.append((total, e))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:top_n]]


def list_all() -> list[dict]:
    """列出所有条目"""
    sk = load_sk()
    return sorted(sk.get("entries", []), key=lambda x: x.get("updated", ""), reverse=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tacit Knowledge Catcher")
    parser.add_argument("--mode", choices=["catch", "inject", "list"], default="list")
    parser.add_argument("--input", help="对话文本（catch 模式）")
    parser.add_argument("--query", help="查询关键词（inject 模式）")
    parser.add_argument("--source", default="manual", help="来源标记")
    args = parser.parse_args()
    
    if args.mode == "catch":
        if not args.input:
            print("❌ --input required for catch mode")
            sys.exit(1)
        results = catch(args.input, args.source)
        if results:
            print(f"✅ 写入 {len(results)} 条:")
            for r in results:
                print(f"  [{r['type']}] {r['key'][:60]}")
        else:
            print("⚠️ 未检测到隐性知识")
    
    elif args.mode == "inject":
        if not args.query:
            print("❌ --query required for inject mode")
            sys.exit(1)
        results = inject(args.query)
        if results:
            print(f"🔍 找到 {len(results)} 条相关知识:\n")
            for r in results:
                print(f"[{r['type']}] {r['key']}")
                if "answer" in r:
                    print(f"  → {r['answer'][:100]}")
                if "conclusion" in r:
                    print(f"  → 结论: {r['conclusion'][:100]}")
                print(f"  来源: {r.get('source','?')} | 更新: {r.get('updated','?')}\n")
        else:
            print("⚠️ 未找到相关知识")
    
    else:  # list
        entries = list_all()
        print(f"📚 shared-knowledge.json 共 {len(entries)} 条:\n")
        for e in entries:
            print(f"[{e['type']}] {e['key'][:60]} | {e.get('updated','?')}")
