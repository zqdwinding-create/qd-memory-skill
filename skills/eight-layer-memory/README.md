# 8 Layer Memory Skill

> **跨通道 + 时间近度 + 跨层融合的 LLM 行为模板**
> 让任何 OpenClaw 知道什么时候写到哪层、怎么查、怎么融合。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)]()
[![Tests: 63 passing](https://img.shields.io/badge/tests-78%20passing-brightgreen.svg)]()

---

## 1 分钟装上

### 方式 A · ClawHub

```bash
clawhub install eight-layer-memory
```

### 方式 B · GitHub

```bash
git clone https://github.com/zqdwinding-create/qd-memory-skill.git
cp -r qd-memory-skill/skills/eight-layer-memory ~/.openclaw/skills/
```

### 方式 C · 本地 tar

```bash
# 源机器
cd ~/.openclaw/skills/
tar czf /tmp/eight-layer-memory-skill.tgz eight-layer-memory/
scp /tmp/eight-layer-memory-skill.tgz user@target:/tmp/

# 目标机器
mkdir -p ~/.openclaw/skills/
cd ~/.openclaw/skills/
tar xzf /tmp/eight-layer-memory-skill.tgz
```

---

## 5 分钟验证

```bash
# 1. SKILL 装上
ls ~/.openclaw/skills/eight-layer-memory/SKILL.md

# 2. 单测全绿
cd ~/.openclaw/skills/eight-layer-memory/scripts/
python3 -m unittest discover tests/ -v 2>&1 | tail -5
# 期望：Ran 63 tests in 0.5s OK

# 3. L9 跨通道搜索
python3 unified-memory-search.py "test" 2>&1 | head -10

# 4. L6 捕捉
python3 tacit-knowledge-catcher.py --mode catch --input "smoke test" --source install-verify
ls ~/.openclaw/workspace/shared-knowledge.json
```

**3 验证全过 = 装成功**

---

## 6 层架构（L 编号保留）

```
L0 上下文      LLM 当前 turn 的 prompt + tools
L1 session    OpenClaw isolated session（per cron / per 子智能体）
L2 核心文件    SOUL.md / USER.md / AGENTS.md / TOOLS.md / IDENTITY.md
L3 daily log  memory/YYYY-MM-DD.md（每日时间序）
L4 raw         conversations/raw/YYYY-MM/*.jsonl（原始 session transcript）
L5 短期        cache_entries SQLite（OpenClaw 内置，TTL）
L6 shared      shared-knowledge.json（隐性知识库，跨通道共享）
L7 向量        memory-core-local-embedding-worker（OpenClaw 内置）
L8 沉淀        MEMORY.md / lessons/system.md（长期经验）
L9 跨层融合    unified-memory-search.py（本 SKILL 提供）
```

**5 步法工作流** = 写 → 存 → 检 → 活 → 化

| 步骤 | 操作 | 层 |
|------|------|----|
| 写 | LLM 把对话关键内容写到对应层 | L2/L3/L4 |
| 存 | L6 自动捕捉（每 2h cron 跑） | L6 |
| 检 | LLM 主动调 L9 unified-memory-search | L9 |
| 活 | L6 + L3 + L4 三角融合回答 | L9 |
| 化 | 长期经验沉淀到 L8 lessons | L8 |

---

## 触发条件（AGENTS.md B+ 类）

在 `~/.openclaw/workspace/AGENTS.md` 加：

```markdown
| **「你记得 / 我之前 / 上次 / 我们讨论过 / 昨天聊过 / 之前说过 / 拍板 / 就这么定了 / 开干 / 6 层 / 记忆体系 / shared-knowledge / tacit / 隐性知识 / 跨通道 / 时间近度 / 跨层融合 / unified-memory-search」** | **eight-layer-memory** | **6 层记忆体系 SKILL**。**5 步法工作流**：写（L2/L3/L4）→ 存（L5/L6）→ 检（L7/L9 跨通道）→ 活（L6+L3+L4 三角融合）→ 化（L8 沉淀）。**路径**：调 `unified-memory-search.py` + `tacit-knowledge-catcher.py`。**默认启用** |
```

---

## 文件结构

```
eight-layer-memory/
├── README.md                          # 本文件
├── LICENSE                            # MIT
├── INSTALL.md                         # 详细安装 SOP
├── SKILL.md                           # SKILL 行为模板（7.8KB）
├── assets/
│   ├── 8-layer-spec.md                # 6 层架构（L 编号保留）详细规范
│   └── templates/                     # 10 个 L2 核心文件模板
├── scripts/                           # 4 个生产脚本 + 3 个单测
│   ├── README.md
│   ├── unified-memory-search.py       # L9 跨层融合
│   ├── tacit-knowledge-catcher.py     # L6 隐性知识捕捉（11KB）
│   ├── l6-incremental-catch.py        # L6 cron 单步（2KB）
│   ├── save-conversations.py          # L4 会话保存（8KB）
│   └── tests/                         # 63 tests
│       ├── test_unified_memory_search.py
│       ├── test_unified_search_e2e.py
│       └── test_tacit_knowledge_catcher.py
└── examples/                          # 3 个最小可运行示例
    └── README.md
```

---

## 设计原则

1. **自包含**：SKILL = 行为模板 + 生产脚本 + 单测，**不依赖外部**
2. **跨用户**：`shared-knowledge.json` 等个人数据**不打包**，新用户装上 = 干净 L6
3. **可移植**：纯 Python 标准库，无外部依赖
4. **可验证**：78 个单测 + 5 分钟端到端验证 SOP
5. **可观察**：L6 / L3 / L4 三角融合 = 跨层召回可视化

---

## 隐私与边界

**装上后会自动创建**：
- `~/.openclaw/workspace/shared-knowledge.json`（**新用户从 0 开始**）
- `~/.openclaw/workspace/memory/YYYY-MM-DD.md`（**今天开始记**）

**绝不复制**（个人数据）：
- ❌ `shared-knowledge.json` 旧内容（含个人隐私）
- ❌ `memory/2026-*.md` daily logs
- ❌ `SOUL.md` / `USER.md` / `IDENTITY.md`

**用户责任**：装上后自己决定 L6 从 0 开始 / 手动导入。

---

## 适用 / 不适用

### ✅ 适用

- LLM 行为模板标准化（让任何 LLM 知道什么时候写到哪层）
- 跨 agent 复用（多个子智能体 + main agent 共享同一套记忆机制）
- 跨用户复用（新用户装上即可，不用重新设计）
- 跨平台（OpenClaw + Claude Code + Cursor + 任何 LLM 工具）

### ❌ 不适用

- 对外发布（SKILL 里的 L6 数据是个人数据）
- 替代向量数据库（这是行为模板层，不是存储层）
- 大数据量场景（> 10000 条 L6 条目需要重设计）

---

## 贡献

- **作者**：8 Layer Memory Skill Contributors
- **方法论**：5 步法工作流（写 → 存 → 检 → 活 → 化）
- **当前状态**：v0.2.0（生产部署验证）
- **License**：MIT
- **下个版本**：v1.1 加 showcase 视频

---

_编制完成 · 2026-06-22 · 6 层体系 SKILL v1 开源版_
