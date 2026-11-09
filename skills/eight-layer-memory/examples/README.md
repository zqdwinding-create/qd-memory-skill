# 6 层体系 SKILL — 3 个最小可运行示例

> **第 4 轮迭代（v0.5 examples）**
> 路径：`skills/eight-layer-memory/examples/`
> 编制：2026-06-22 10:20

---

## 示例 1 · 基本捕捉（L2 + L3 + L4）

### 场景

用户在 Telegram 说了一句"今天做了什么"——LLM 自动写入 L3 daily log，同时 L4 raw transcript 自动记录。

### 步骤

```bash
# 1. 用户说"今天做了什么"
# 2. LLM 自动响应 → 调用 L3 write 模式
# 3. LLM 自动响应 → 触发 L4 transcript 自动记录（OpenClaw 内置）
```

### 期望输出

```markdown
# 2026-06-22 每日日志

## [HH:MM] Telegram — 问"今天做了什么"

### 用户 HH:MM
> "今天做了什么"

### 助手 HH:MM
[按时间序列出当天事件]
```

### 验证

```bash
ls ~/.openclaw/workspace/memory/$(date +%Y-%m-%d).md
# 应存在当天 daily log 文件
```

---

## 示例 2 · 跨通道搜索（L9 unified-memory-search）

### 场景

用户在 Telegram 问"你记得我昨天说的那个 L9 搜索吗"——LLM 自动调 L9 跨通道搜索。

### 步骤

```bash
# 1. 用户问"你记得..."
# 2. LLM 检测到"你记得/我之前/上次" → 触发 L9
# 3. 调 unified-memory-search.py
python3 ~/.openclaw/workspace/scripts/unified-memory-search.py "记忆 SKILL"

# 4. 收到结果（含来源引用）
# 5. LLM 引用 L6 / L3 / L4 多层结果回答
```

### 期望输出

```
=== L9 搜索结果 ===
Top 1: [shared-knowledge cap-<id>]
  - key: "项目部署记录查询..."
  - updated: <date>
  - channel: feishu
  - score: 0.92

Top 2: [daily log <date>]
  - key: "记忆技能评估..."
  - updated: <date>
  - channel: telegram
  - score: 0.85
```

### 验证

```bash
# 直接跑 L9 验证
python3 ~/.openclaw/workspace/scripts/unified-memory-search.py "记忆 SKILL"
# 应输出 Top N 结果（含 channel + date 引用）
```

---

## 示例 3 · 多通道隔离（默认只查当前通道）

### 场景

用户在 Telegram 问"你记得微信那边我说了什么吗"——LLM **不主动跨通道**，但用户明示"跨通道"时查询所有通道。

### 步骤

```bash
# 1. 用户问"微信那边我说了什么"
# 2. LLM 检测"我说了什么" → 默认只查当前 channel（telegram）
# 3. 如用户明示"跨通道"或"5 通道全搜" → 跨通道
```

### 期望输出（默认通道隔离）

```
=== L9 搜索（当前通道 = telegram） ===
[无结果 — telegram 没相关条目]

=== 提示 ===
未在当前通道（telegram）找到。要不要跨通道搜？（5 通道全搜）
```

### 期望输出（明示跨通道）

```
=== L9 搜索（5 通道全搜） ===
Top 1: [shared-knowledge ...]
  - channel: wechat
  - updated: <date>
```

### 验证

```bash
# 默认通道隔离
python3 unified-memory-search.py "查询词" --channel telegram
# 跨通道
python3 unified-memory-search.py "查询词" --all-channels
```

---

## 工作约定（examples 通用）

- **最小可运行**：每个示例必须有可跑的步骤 + 期望输出 + 验证命令
- **5 分钟跑通**：从 0 到结果不超过 5 分钟
- **可截图**：每个示例可生成截图供 showcase 用（待 v0.5+ 阶段）

---

_编制完成 · 6 层体系 SKILL v1 examples 阶段_