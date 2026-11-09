# 6 层体系核心脚本

> **scripts 配套索引档** · 6 层记忆体系 SKILL 配套（MIT License）
> 路径：`skills/eight-layer-memory/scripts/`
> 编制：2026-06-22 21:05
> 重要：**SKILL 自包含脚本源码**（4 个生产脚本 + 3 个单测 = 7 文件）

---

## 1. 4 个核心脚本（自包含，SKILL 直接带）

### L9 · unified-memory-search.py

- **路径**：`skills/eight-layer-memory/scripts/unified-memory-search.py`
- **用途**：跨通道 + 时间加权 + 跨层融合召回
- **算法**：
  ```
  score = semantic_similarity × channel_weight × time_decay × type_boost
  ```
- **依赖**：纯 Python 标准库
- **单测**：`scripts/tests/test_unified_memory_search.py` + `test_unified_search_e2e.py`（63 tests）
- **调用**：
  ```bash
  python3 unified-memory-search.py "查询词"
  ```

### L6 · tacit-knowledge-catcher.py

- **路径**：`skills/eight-layer-memory/scripts/tacit-knowledge-catcher.py`
- **用途**：5 类型自动检测 + 隐性知识捕捉
- **5 类型**：system-config / project-state / conclusion / capability / conversation-topic
- **依赖**：纯 Python 标准库
- **单测**：`scripts/tests/test_tacit_knowledge_catcher.py`
- **调用**：
  ```bash
  python3 tacit-knowledge-catcher.py --mode catch --input "对话文本"
  ```

### L6 · l6-incremental-catch.py

- **路径**：`skills/eight-layer-memory/scripts/l6-incremental-catch.py`
- **用途**：单步 bash 友好的 L6 自动更新（不靠 LLM 跑多步）
- **流程**：读 daily log → 喂 tkc catch → 写 L6
- **被 L6 增量更新 cron 调用**
- **依赖**：纯 Python 标准库

### L4 · save-conversations.py

- **路径**：`skills/eight-layer-memory/scripts/save-conversations.py`
- **用途**：会话保存（脚本 v2 — daily log 增量保存）
- **L4 作用**：sessions/*.jsonl → memory/YYYY-MM-DD.md
- **依赖**：纯 Python 标准库
- **调用**：
  ```bash
  python3 save-conversations.py
  ```

---

## 2. 单测套件（自包含，3 个文件）

```
scripts/tests/
├── test_unified_memory_search.py     # L9 单元测试
├── test_unified_search_e2e.py         # L9 端到端测试
└── test_tacit_knowledge_catcher.py    # L6 单元测试
```

**运行**：
```bash
cd skills/eight-layer-memory/scripts/
python3 -m unittest discover tests/ -v
# 期望：63 tests 全绿
```

---

## 3. 安装策略（重要）

**SKILL 自包含脚本** —— 装 SKILL 时自动带上 scripts/。

```bash
# 安装方式 1：clawhub
clawhub install eight-layer-memory

# 安装方式 2：git
git clone https://github.com/zqdwinding-create/qd-memory-skill.git
cp -r qd-memory-skill/skills/eight-layer-memory ~/.openclaw/workspace/skills/

# 验证脚本在 SKILL 里
ls skills/eight-layer-memory/scripts/{unified-memory-search,tacit-knowledge-catcher,save-conversations,l6-incremental-catch}.py
```

**为什么自包含**：
- ✅ 装 SKILL = 装脚本（一步到位）
- ✅ SKILL 可独立工作（不依赖外部）
- ✅ 跨用户开箱即用
- ⚠️ 缺点：脚本更新时 SKILL 版本要 bump

---

## 4. 工作约定

- **commit 即 push**：脚本改动立刻 push（不囤本地 commit）
- **闪断保护**：state.json + atomic write 模式
- **L6 校验**：数据校验脚本 v0.3 提供
- **L9 调用日志**：每次跑记入 daily log
- **脱敏铁律**：发外部版本前必须扫用户个人信息（用户名/公司/家庭住址等）

---

_编制完成 · 6 层体系 SKILL v1 scripts 阶段（开源版）_