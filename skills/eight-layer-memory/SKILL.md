---
name: eight-layer-memory
displayName: 6 层记忆体系 · 跨通道记忆 SKILL
version: 0.2.0
status: v0.2.0
description: |
  6 层记忆体系 — 跨通道 + 时间近度 + 跨层融合的 LLM 行为模板。
  让 LLM 知道什么时候写到哪层、怎么查、怎么融合。

  6 层存储 = L0 上下文 / L1 session / L2 核心文件 / L3 daily log / L4 raw / L6 shared / L8 沉淀 / L9 跨层融合；引用层 2 个：L5（已由 L9 替代）、L7（内置检索）。
  工作流 5 步 = 写 → 存 → 检 → 活 → 化。
  触发词：6 层 / 记忆 / 检索 / 知识库 / tacit / shared-knowledge / 跨通道 / 跨层融合 / unified-memory-search。
  边界：用户自己的 L6 shared-knowledge 数据（含个人/家庭/工作信息）属于私有数据，不应提交到公开仓库；本仓库只包含行为模板与工具，不含任何用户数据。
  工作约定：按 5 步法工作流，不脱胎换骨，不改 6 层本身的算法和脚本。
  联动：cron 集成（每 30 分钟 L9 跑一次）/ 子智能体 toolsAllow 配两处 / 主会话 AGENTS.md B+ 类触发条件。
---

# 6 层记忆体系 · 跨通道记忆 SKILL

> **工作约定**
> 这块 SKILL 是"6 层体系"的**行为模板**，**不是脱胎换骨**——
> 只让 LLM 知道什么时候写到哪层 / 怎么查 / 怎么融合，**不改 6 层本身的算法和脚本**。
> 5 步工作流是"记忆生命周期"，不是"打磨流程"。

## 适用 / 不适用

### ✅ 适用

- LLM 行为模板标准化（让任何 LLM 知道什么时候写到哪层）
- 跨 agent 复用（多个子智能体与 main agent 共享同一套记忆机制）
- 行为可被外部审计（SKILL.md + 配套脚本形成可审计资产）
- 个人知识管理（单用户私有部署）

### ❌ 不适用

- 公开分享你自己的 shared-knowledge.json（个人/家庭/工作信息不应公开）

- 实时对话响应（不在 5 步工作流范围）
- 跨框架移植（这是 OpenClaw 特定实现）

---

## 5 步法工作流

### 第 1 步 · **写** — 写到 L2-L4

| 层 | 写到哪里 | 例子 |
|----|---------|------|
| **L2 核心文件** | AGENTS.md / SOUL.md / USER.md / IDENTITY.md / TOOLS.md / MEMORY.md / TODO.md / PROBLEM.md | 8 类核心文件是"工作区骨架" |
| **L3 每日日志** | `memory/YYYY-MM-DD.md` | 每天会话的"现场" |
| **L4 原始记录** | `sessions/*.jsonl`（自动） | 全量会话原始数据 |

**触发场景**：
- 收到"要改 AGENTS.md" → 写到 L2
- "今天做了什么" → 写到 L3 daily log
- 任何 LLM 行为 → 自动 L4 记录

### 第 2 步 · **存** — 自动捕捉到 L5-L6

| 层 | 存什么 | 算法 |
|----|--------|------|
| **L5 短期记忆** | `short-term-recall.json`（9 天窗口） | 已被 L9 替代，仅做兼容 |
| **L6 shared-knowledge** | `config/shared-knowledge.json`（结构化条目） | 5 类型自动检测 |

**L6 5 类型 ID 前缀约定**：
- `sys-`（system-config）— 系统配置
- `pro-`（project-state）— 项目状态
- `cap-`（capability）— 能力/工具
- `con-`（conclusion）— 结论
- `conversation-topic` — 对话主题

**触发场景**：
- 涉及系统配置 → 自动归 `sys-`
- 涉及项目进度 → 自动归 `pro-`
- 涉及能力/工具 → 自动归 `cap-`
- 涉及经验结论 → 自动归 `con-`

### 第 3 步 · **检** — 跨通道搜索（L7-L9）

| 层 | 检什么 | 算法 |
|----|--------|------|
| **L7 向量搜索** | Gemini embedding | OpenClaw 内置 |
| **L9 unified-memory-search** | 跨通道 + 时间加权 | 多通道并行 |

**L9 三层防御（α/β/γ）**：
- α：AGENTS.md 硬约束（不准用旧 API）
- β：plugin 替换（统一 wrapper）
- γ：SKILL.md 软规范（本文件）

**L9 加权公式**：
```
score = semantic_similarity × channel_weight × time_decay × type_boost
```

- `channel_weight`：5 通道排序加分（当前 channel +1000）
- `time_decay`：7d+5 / 30d+2 / 老+0
- `type_boost`：5 类型分布调节

**触发场景**：
- 任何"我之前..." / "上次..." / "你记得..." → 调 L9
- 通道隔离：默认只查当前通道（如要跨通道，明确说"5 通道全搜"）

### 第 4 步 · **活** — 跨层融合召回

**L6 + L3 + L4 三角融合**（不依赖单一向量）：
- L6（结构化）：shared-knowledge（结构化条目）
- L3（半结构化）：daily log（每天 1 份）
- L4（非结构化）：raw transcript（会话转录文件）

**隐性知识自动捕捉**（5 类型检测）：
- 修复案例沉淀（tacit-knowledge 实战）
- 跨通道"lifecycle" 排序
- 命中后立即 cite 来源（channel + 日期 + 文件）

**触发场景**：
- 用户问"我之前说...什么来着" → L6 + L3 + L4 三角查
- LLM 主动 cite："根据 2026-06-21 Telegram ..."

### 第 5 步 · **化** — 经验沉淀到 L8

| 层 | 化到哪里 | 例子 |
|----|---------|------|
| **L8 知识沉淀** | `taskreports/项目/` | 项目级报告 |
| **L8 经验教训** | `memory/lessons/system.md` | 教训 1-90 详细版 |
| **L8 长文** | Obsidian Vault | 跨日笔记 / 录音 / 草稿 |
| **L8 索引** | `MEMORY.md` Top 15 速查 | 教训精简版 |

**触发场景**：
- "记下这个教训" → 写到 `lessons/system.md`
- "完整复盘" → 写到 `taskreports/项目/`
- "长文/录音" → 写到 Obsidian Vault

---

## 触发词

包括但不限于：
- **6 层** / 记忆体系 / 跨层融合
- **记忆** / 检索 / 知识库 / shared-knowledge
- **tacit** / 隐性知识 / 暗知识
- **跨通道** / 多通道 / channel isolation
- **时间近度** / 时间加权
- **unified-memory-search** / 跨层融合

## 联动

| 联动对象 | 怎么联 | 状态 |
|---------|--------|------|
| **cron 集成** | 每 30 分钟 L9 unified-memory-search 自动跑一次 | ⏳ 待 H1 |
| **子智能体** | 各子智能体调 SKILL，toolsAllow 配两处 | ⏳ 待 H2 |
| **主会话** | AGENTS.md B+ 类加触发条件 + daily log 自动引用 | ⏳ 待 H3 |

---

## 工作纪律

- **commit 即 push**：6 层体系脚本改动立刻 push（不囤本地 commit）
- **闪断保护**：state.json + atomic write 模式（已实现，待测）
- **L6 校验**：每周跑一次 `shared-knowledge-cleanup.py（v0.3 提供）`
- **L9 调用日志**：每次跑记入 daily log
- **不泄露隐私**：SKILL.md / 脚本 / 测试数据中**绝不**出现真实 API key / token / 私人路径 / 真实账号

---

## 验收标准

✅ SKILL 化完成标准（9 维评分 ≥ 70/90）：

| 维度 | 目标 | 当前 |
|------|------|------|
| 结构·SKILL.md 完整度 | ≥ 8/10 | 0/10 → v0 后 ~6/10 |
| 结构·6 层架构（L 编号保留）文档 | ≥ 8/10 | 8/10 ✅ |
| 结构·核心文件模板 | ≥ 8/10 | 9/10 ✅ |
| 实测·L9 单测覆盖 | ≥ 6/10 | 5/10 |
| 实测·L6 单测覆盖 | ≥ 6/10 | 5/10 |
| 实测·跨层融合 E2E | ≥ 6/10 | 4/10 |
| 活体·自我迭代 | ≥ 8/10 | 9/10 ✅ |
| 活体·真实场景调用 | ≥ 8/10 | 6/10 |
| 活体·L6 激活 | ≥ 8/10 | 3/10 |

**当前总分**：49/90 = 54%（v0 SKILL.md 后预估 55/90）

**v1 目标**：补 D1-D3 单测 + 激活 L6 → 70/90 验收达标

---

## v0 → v1 路线图

- [ ] v0.1：本文件（SKILL.md 草稿）✅
- [ ] v0.2：补 `assets/8-layer-spec.md`（架构规范独立成档）
- [ ] v0.3：补 `assets/templates/`（8 类核心文件模板）
- [ ] v0.4：补 `scripts/` 链接（3 核心脚本 + L6 cleanup）
- [ ] v0.5：补 `examples/`（3 最小可运行示例）
- [ ] v0.6：补 9 维评分（v0 自检 + 第三方视角）
- [ ] v1.0：基线评分 ≥ 70/90 → 验收达标

---

_文档版本：2026-06-22_
_编制：Six-Layer Memory Skill Contributors（MIT License）_
_方法论：5 步法工作流（写 → 存 → 检 → 活 → 化）_
_当前状态：v0.2.0（含 L6 自动更新 + 跨用户可安装）_
_安装方法：见 `INSTALL.md` 或 GitHub `zqdwinding-create/qd-memory-skill`_

## 变更记录

### v0.2.0（2026-11-09 回传）
- unified-memory-search.py：合入本地实战迭代版（34KB）——`--channel` 通道隔离过滤（tg/fs/wx/qqbot 别名）、`--date/--yesterday/--since/--until` 时间过滤、`--json` 结构化输出；新增"逻辑日"切换点（凌晨 4:00，逻辑日窗口 = [昨天04:00, 今天04:00)）
- 落点：AGENTS.md 硬约束引用此脚本为记忆检索唯一入口；与内置 active-memory 的分流决策表见 AGENTS.md「记忆搜索」节
- 状态修正：L5 短期记忆已废弃（被本脚本替代）、L7 为内置检索引用——对外表述"6 层存储 + 2 层引用"

## 路线图
