#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md5 对账工具 — 检测本地安装 skill 与 GitHub 仓工作副本的漂移

Phase4 防漂移机制（2026-11-16 立）：月度（或任意时机）对账本地安装目录
~/.openclaw/skills/eight-layer-memory/ 与本仓工作副本的同名文件，
md5 不一致即给出 diff 摘要，防「三套版本并存」复发。

用法：
  python3 tools/md5_audit.py                    # 默认对账 SKILL.md
  python3 tools/md5_audit.py <仓内相对路径> ...  # 对账其他文件（相对仓根，须在 skill 安装目录有同名文件）

退出码：0 = 全部一致；1 = 存在漂移（可直接挂月度定时检查）
纯 Python 标准库，只读，不修改任何文件。
"""

import difflib
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_SKILL_DIR = Path.home() / ".openclaw/skills/eight-layer-memory"
DIFF_MAX_LINES = 20  # diff 摘要最多显示行数


def md5sum(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def audit(rel: str) -> bool:
    """对账单个文件。返回 True = 一致。"""
    repo_file = REPO_ROOT / rel
    # 仓内 skill 文件 ↔ 本地安装目录同名文件
    prefix = "skills/eight-layer-memory/"
    if rel.startswith(prefix):
        local_file = LOCAL_SKILL_DIR / rel[len(prefix):]
    else:
        local_file = LOCAL_SKILL_DIR.parent / rel  # 非 skill 文件按相对结构退化为无效对
        print(f"⚠️  {rel}: 不在 skills/eight-layer-memory/ 下，跳过（本工具只对账 skill 安装目录）")
        return True

    print(f"── {rel}")
    if not repo_file.exists():
        print(f"   ❌ 仓内不存在: {repo_file}")
        return False
    if not local_file.exists():
        print(f"   ❌ 本地安装目录不存在: {local_file}")
        return False

    r_md5, l_md5 = md5sum(repo_file), md5sum(local_file)
    if r_md5 == l_md5:
        print(f"   ✅ 一致  md5={r_md5[:12]}…")
        return True

    print(f"   🔴 漂移！仓 md5={r_md5[:12]}…  本地 md5={l_md5[:12]}…")
    repo_text = repo_file.read_text(errors="replace").splitlines()
    local_text = local_file.read_text(errors="replace").splitlines()
    diff = list(difflib.unified_diff(
        local_text, repo_text,
        fromfile=f"local:{local_file.name}", tofile=f"repo:{repo_file.name}", lineterm="",
    ))
    if diff:
        print(f"   📄 diff 摘要（前 {DIFF_MAX_LINES} 行 / 共 {len(diff)} 行）:")
        for line in diff[:DIFF_MAX_LINES]:
            print(f"   {line}")
        if len(diff) > DIFF_MAX_LINES:
            print(f"   …（其余 {len(diff) - DIFF_MAX_LINES} 行省略，用 diff 命令看全量）")
    return False


def main() -> int:
    targets = sys.argv[1:] or ["skills/eight-layer-memory/SKILL.md"]
    print(f"🔍 md5 对账：仓 {REPO_ROOT}")
    print(f"   ↔ 本地安装 {LOCAL_SKILL_DIR}\n")
    results = [audit(rel) for rel in targets]
    ok = sum(1 for r in results if r)
    total = len(results)
    drift = total - ok
    print(f"\n📊 结论：{ok}/{total} 一致" + (f"，{drift} 项漂移" if drift else "，无漂移"))
    if drift:
        print("   处置：确认哪边是最新 → 手动同步 → 重跑本工具验证")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
