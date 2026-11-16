# 6 层体系核心脚本

> **scripts 配套索引档** · 6 层记忆体系 SKILL 配套（MIT License）
> 路径：`skills/eight-layer-memory/scripts/`
> 编制：2026-06-22 21:05
> 重要：**SKILL 自包含脚本源码**（5 个生产脚本 + 3 个单测 = 8 文件）

---

## 1. 5 个核心脚本（自包含，SKILL 直接带）

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

### L6 · shared-knowledge-cleanup.py

- **路径**：`skills/eight-layer-memory/scripts/shared-knowledge-cleanup.py`
- **用途**：L6 信噪比清理——低质量条目打分归档到 archive 文件，**不删除原数据**（apply 前自动备份）
- **评分维度**：type 合法性 / id 前缀与 type 匹配 / 字段对齐 / 内容长度 / 时间近度
- **依赖**：纯 Python 标准库
- **调用**：
  ```bash
  python3 shared-knowledge-cleanup.py              # 默认 dry-run，只打印报告
  python3 shared-knowledge-cleanup.py --apply      # 实际归档低分条目
  ```

### L4 · save-conversations.py

- **路径**：`skills/eight-layer-memory/scripts/save-conversations.py`
- **用途**：会话保存（脚本 v5 — 增量追加 + SQLite 索引重建 + WAL 三件套防撕裂拷贝 + 临时文件清理）
- **L4 作用**：agents/main/sessions 会话转录 → conversations/raw/YYYY-MM/*.jsonl（物化目录，L9 扫描源）
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
cp -r qd-memory-skill/skills/eight-layer-memory ~/.openclaw/skills/

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
- **L6 校验**：`shared-knowledge-cleanup.py` 随 SKILL 分发（每周跑一次）
- **L9 调用日志**：每次跑记入 daily log
- **脱敏铁律**：发外部版本前必须扫用户个人信息（用户名/公司/家庭住址等）

---

_编制完成 · 6 层体系 SKILL v1 scripts 阶段（开源版）_