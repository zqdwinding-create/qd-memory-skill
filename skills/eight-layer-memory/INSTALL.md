# 6 层体系 SKILL · 安装 SOP

> **目标**：在另一台服务器/另一个 OpenClaw 上把 6 层记忆体系跑起来
> **编制**：Six-Layer Memory Skill Contributors
> **版本**：v1（2026-06-22 编制）
> **5 分钟可跑通**（假设已有 OpenClaw + Python 3.10+）

---

## 0 · 装之前必看

### SKILL vs 脚本的关系

| 类别 | 内容 | 路径 |
|------|------|------|
| **SKILL（行为模板）** | 让 LLM 知道 6 层怎么用、什么时候调什么 | `skills/eight-layer-memory/` |
| **生产脚本（3 个）** | 真正干活的工具 | `~/.openclaw/skills/eight-layer-memory/scripts/` |
| **数据文件（L6）** | 隐性知识库 | `~/.openclaw/workspace/shared-knowledge.json` |

**两者必须都装**：
- 只装 SKILL → LLM 知道怎么做但没工具可调 ❌
- 只装脚本 → 工具在但 LLM 不知道什么时候用 ❌

### 不装什么

- ❌ **不复制 `shared-knowledge.json`**（含个人/家庭/工作隐私，跨用户 0 价值）
- ❌ **不复制 `memory/2026-*.md` daily logs**（含个人对话，跨用户 0 价值）
- ❌ **不复制 `agents/main/jobs.json` 备份**（cron 任务含路径/账号）
- ❌ **不复制 `~/.openclaw/workspace/SOUL.md` `USER.md` `IDENTITY.md`**（含用户身份）

---

## 1 · 装 SKILL（自包含：行为模板 + 4 个脚本 + 3 个单测）

### 1.1 从 GitHub 克隆（推荐）

```bash
# 目标机器
git clone https://github.com/zqdwinding-create/qd-memory-skill.git /tmp/qd-memory-skill
mkdir -p ~/.openclaw/skills/
cp -r /tmp/qd-memory-skill/skills/eight-layer-memory ~/.openclaw/skills/
```

### 1.2 从 ClawHub 安装

```bash
# 目标机器
clawhub install eight-layer-memory
```

### 1.3 从本地 tar 装（内测/私有场景）

```bash
# 源机器打 tar
cd ~/.openclaw/skills/
tar czf /tmp/eight-layer-memory-skill.tgz eight-layer-memory/
scp /tmp/eight-layer-memory-skill.tgz user@target:/tmp/

# 目标机器解压
mkdir -p ~/.openclaw/skills/
cd ~/.openclaw/skills/
tar xzf /tmp/eight-layer-memory-skill.tgz
```

### 1.4 验证 SKILL 装上

```bash
# 1. SKILL.md 存在
ls -la ~/.openclaw/skills/eight-layer-memory/SKILL.md

# 2. 4 个脚本都装上
ls ~/.openclaw/skills/eight-layer-memory/scripts/{unified-memory-search,tacit-knowledge-catcher,save-conversations,l6-incremental-catch}.py

# 3. 3 个单测都装上
ls ~/.openclaw/skills/eight-layer-memory/scripts/tests/*.py

# 4. 跑单测（验证 63 tests 全绿）
cd ~/.openclaw/skills/eight-layer-memory/scripts/
python3 -m unittest discover tests/ -v 2>&1 | tail -10
```

**期望**：`Ran 63 tests in 0.5s OK`

**注意**：如果 OpenClaw 用了 skill 白名单机制，需要在 `openclaw.json` `agents.list[].skills` 加 `eight-layer-memory`，并在 `agent.json` `toolsAllow` 加它。**详见第 4 节**。

---

## 2 · 环境要求

- Python 3.10+
- OpenClaw（已配置 agent）
- git

## 3 · 装 L6 自动更新 cron

### 3.1 复制 cron 任务定义

```bash
# 源机器：找 L6 增量更新 cron 任务定义
python3 -c "
import json
d = json.load(open('~/.openclaw/cron/jobs.json'))
for j in d.get('jobs', []):
    if 'l6' in j.get('name', '').lower():
        # 去掉 state 字段
        j.pop('state', None)
        print(json.dumps(j, indent=2, ensure_ascii=False))
        break
" > /tmp/l6-cron-job.json
```

```bash
# 目标机器：手动注册（OpenClaw 没有跨机 cron 同步 API）
# 通过 OpenClaw 配置工具或直接编辑 jobs.json 后重启 gateway
```

### 3.2 简化的 L6 触发方式（推荐）

**如果目标机器 OpenClaw 还在初始化**，**优先**用 LLM 行为模式：
- LLM 在对话中检测到"刚才说的" → 调 tkc catch
- 不需要 cron 也能跑

**3.3 完整的 L6 自动化（生产模式）**：
- 每 2h 偶数点跑 l6-incremental-catch.py
- 需要目标机器设好 cron

---

## 4 · 配置 skill 白名单

### 4.1 main agent（必须）

```bash
# 目标机器编辑 ~/.openclaw/openclaw.json
# 在 agents.list[0].skills 加 "eight-layer-memory"
# 在 agents.list[0].toolsAllow 加 "eight-layer-memory"
```

### 4.2 子智能体（按需）

如果目标机器有子智能体，每个 agent.json 的 `toolsAllow` 都要加。

### 4.3 AGENTS.md B+ 类触发条件（关键！）

**SKILL 装上不等于 LLM 会用**，必须给 LLM 触发条件：

在 `~/.openclaw/workspace/AGENTS.md` 加：

```markdown
| **「你记得 / 我之前 / 上次 / 我们讨论过 / 昨天聊过 / 之前说过 / 拍板 / 就这么定了 / 开干 / 6 层 / 记忆体系 / shared-knowledge / tacit / 隐性知识 / 跨通道 / 时间近度 / 跨层融合 / unified-memory-search」** | **eight-layer-memory** | **6 层记忆体系 SKILL**。**5 步法工作流**：写（L2/L3/L4）→ 存（L5/L6）→ 检（L7/L9 跨通道）→ 活（L6+L3+L4 三角融合）→ 化（L8 沉淀）。**路径**：调 `unified-memory-search.py` + `tacit-knowledge-catcher.py` + 9 维评分验收标准。**默认启用** |
```

**位置**：AGENTS.md 的"技能加载"段（参考源机器）。

---

## 5 · 端到端验证（5 分钟跑通）

### 5.1 步骤 1：装完 SKILL + 脚本

```bash
ls ~/.openclaw/skills/eight-layer-memory/SKILL.md
ls ~/.openclaw/skills/eight-layer-memory/scripts/unified-memory-search.py
```

### 5.2 步骤 2：跑 L9 验证

```bash
python3 ~/.openclaw/skills/eight-layer-memory/scripts/unified-memory-search.py "test" 2>&1 | head -20
# 期望：0 命中（空环境）+ 提示 "找到 0 条结果"
```

### 5.3 步骤 3：跑 L6 验证

```bash
python3 ~/.openclaw/skills/eight-layer-memory/scripts/tacit-knowledge-catcher.py --mode catch --input "今天测试了 6 层 SKILL 装到新机器上" --source install-test

# 期望：✅ 写入 1 条 + L6 文件含这条

ls ~/.openclaw/workspace/shared-knowledge.json
python3 -c "import json; d=json.load(open('~/.openclaw/workspace/shared-knowledge.json')); print(f'总条数: {len(d[\"entries\"])}')"
```

### 5.4 步骤 4：LLM 行为测试

在目标机器的 OpenClaw 主对话中问：
> "你记得 6 层记忆体系吗？"

**期望 LLM 回答**：引用 SKILL.md + 提到 5 步法工作流 + 主动调 L9 搜索。

### 5.5 步骤 5：AGENTS.md 触发条件测试

在主对话中发：
> "6 层记忆怎么用？"

**期望 LLM 回答**：自动加载 SKILL.md 行为模板 + 列出 L0-L9 + 给具体调用命令。

---

## 6 · 故障排查

### 故障 1：LLM 不调 L9

- **症状**：用户问"你记得..."，LLM 不调 ums.py
- **原因**：AGENTS.md 没加触发条件 OR toolsAllow 没配
- **解决**：按第 4 节配

### 故障 2：L9 报 ModuleNotFoundError

- **症状**：`No module named 'unified_memory_search'`
- **原因**：脚本被复制但 cwd 错
- **解决**：用 `cd ~/.openclaw/workspace/scripts && python3 unified-memory-search.py "test"` 跑

### 故障 3：L6 文件不创建

- **症状**：tkc catch 报"权限错误"
- **原因**：`~/.openclaw/workspace/` 目录权限
- **解决**：`chmod 755 ~/.openclaw/workspace/`

### 故障 4：cron 不触发

- **症状**：L6 增量更新 cron 任务不跑
- **原因**：OpenClaw gateway 没启动 / cron 表达式错
- **解决**：`openclaw gateway status` + `openclaw cron list`

---

## 7 · 跨用户注意（重要）

**6 层体系是 LLM 行为模板，可以跨用户复用**：
- ✅ SKILL.md / 8-layer-spec.md / 9 维评分 / 模板 = **通用**
- ✅ 3 个脚本 = **通用**（不依赖用户数据）
- ❌ shared-knowledge.json = **个人数据，绝不复制**
- ❌ daily logs = **个人数据，绝不复制**
- ❌ SOUL.md / USER.md / IDENTITY.md = **个人身份，绝不复制**

**新用户装上 = 干净的 L6（0 条） + 干净的 daily log（今天开始记） + 干净的 6 层 SKILL（通用行为模板）**。

---

## 8 · 速查：3 个验证命令

```bash
# 1. SKILL 装上
head -3 ~/.openclaw/skills/eight-layer-memory/SKILL.md

# 2. 脚本可跑
python3 ~/.openclaw/skills/eight-layer-memory/scripts/unified-memory-search.py "test" 2>&1 | head -5

# 3. L6 工作
python3 ~/.openclaw/skills/eight-layer-memory/scripts/tacit-knowledge-catcher.py --mode catch --input "smoke test" --source install-verify
python3 -c "import json; d=json.load(open('~/.openclaw/workspace/shared-knowledge.json')); print(len(d['entries']))"
```

**3 个全过 = 装成功**。

---

## 9 · 编制说明

- **编制**：Six-Layer Memory Skill Contributors
- **5 分钟可跑通**：从 tar 包解压到 3 个验证命令全绿
- **5 个分类**：(1) SKILL 装 (2) 脚本装 (3) cron 装 (4) 白名单配 (5) 端到端验证
- **不变量**：跨用户只装"通用部分"，不复制任何"个人数据"
- **3 个常见错误**：toolsAllow 漏配、AGENTS.md 漏触发条件、shared-knowledge.json 误复制
- **下个版本**：v1.1 补全测试覆盖 + 6 个 L2 核心文件模板扩展

---

_编制完成 · 2026-06-22 19:37 · 6 层体系 SKILL v1 验收通过后第 1 份正式交付物_
